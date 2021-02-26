import re
import os
import json
import sys
import traceback
from hashlib import sha1
from queue import Queue, Empty
from threading import Thread
from itertools import zip_longest
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from google.ads.google_ads.client import GoogleAdsClient
from google.api_core import protobuf_helpers

from .banner import banner
from .auth import load_user_auth, load_organization_auth

cache_directory = os.path.join(
    os.getenv('HOME'), '.cache', 'sem-emergency-stop'
)

blob_directory = os.path.join(cache_directory, 'blobs')
match_customer_id = re.compile(r'^customers/\d+/customerClients/(\d+)$').match


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


def parse_customer_id(resource_name):
    return int(match_customer_id(resource_name).group(1))


def query(service, customer_id, query):
    return service.search_stream(str(customer_id), query)


def collect_customer_ids(client):
    service = client.get_service('GoogleAdsService', version='v6')
    return [
        parse_customer_id(row.customer_client.resource_name)
        for response in query(
            service,
            client.login_customer_id,
            'SELECT customer.id FROM customer_client',
        )
        for row in response.results
    ]


def load_blob(sha1_hash):
    with open(os.path.join(blob_directory, sha1_hash), 'rb') as f:
        return json.load(f)


def load_campaign_sets(sha1_hash):
    return load_blob(sha1_hash)['campaign_sets']


def store_blob(obj):
    data = json.dumps(obj, sort_keys=True).encode('utf-8')
    sha1_hash = sha1(data).hexdigest()
    with open(os.path.join(blob_directory, sha1_hash), 'wb') as f:
        f.write(data)

    return sha1_hash


def store_customer_campaign_set(customer_id, campaign_ids):
    return store_blob(
        {
            'customer_id': customer_id,
            'campaign_ids': sorted(campaign_ids),
        }
    )


def store_campaign_sets(campaign_sets):
    return store_blob(
        {
            'campaign_sets': sorted(campaign_sets),
        }
    )


def collect_campaign_ids(client, customer_id):
    service = client.get_service('GoogleAdsService', version='v6')
    return [
        row.campaign.id
        for response in query(
            service,
            customer_id,
            """
                SELECT campaign.id
                FROM campaign
                WHERE
                campaign.status = 'ENABLED'
                AND campaign.experiment_type = 'BASE'
                AND campaign.advertising_channel_type != 'VIDEO'
                AND campaign.advertising_channel_type != 'LOCAL'""",
        )
        for row in response.results
    ]


def retrieve_campaign_ids(client, verbose, customer_ids, campaign_sets):
    while True:
        try:
            customer_id = customer_ids.get_nowait()
        except Empty:
            return

        ids = collect_campaign_ids(client, customer_id)
        campaign_set = store_customer_campaign_set(customer_id, ids)
        campaign_sets.put(campaign_set)
        if verbose:
            print(f"found {len(ids)} campaign(s) for customer {customer_id}")
        customer_ids.task_done()


def get_operation(client, service, customer_id, campaign_id, is_pause):
    operation = client.get_type('CampaignOperation', version='v6')
    campaign = operation.update
    campaign.resource_name = service.campaign_path(customer_id, campaign_id)
    enum = client.get_type('CampaignStatusEnum', version='v6')
    campaign.status = enum.PAUSED if is_pause else enum.ENABLED
    operation.update_mask.CopyFrom(protobuf_helpers.field_mask(None, campaign))

    return operation


def mutate_campaigns(
    client,
    service,
    sha1_hash,
    verbose,
    no_dry_run,
    is_pause,
    campaign_set_queue,
):
    campaign_set = load_blob(sha1_hash)
    customer_id = campaign_set['customer_id']
    campaign_ids = campaign_set['campaign_ids']
    if not campaign_ids:
        return

    for chunk in grouper(campaign_ids, 1000):
        operations = [
            get_operation(client, service, customer_id, campaign_id, is_pause)
            for campaign_id in chunk
            if campaign_id
        ]

        if verbose:
            print(
                f'mutating {len(operations)} campaign(s) '
                f'for customer {customer_id}'
            )
        service.mutate_campaigns(
            str(customer_id), operations, validate_only=not no_dry_run
        )


def mutate_worker(client, verbose, no_dry_run, is_pause, campaign_set_queue):
    service = client.get_service('CampaignService', version='v6')

    while True:
        try:
            sha1_hash = campaign_set_queue.get_nowait()
        except Empty:
            return

        try:
            mutate_campaigns(
                client,
                service,
                sha1_hash,
                verbose,
                no_dry_run,
                is_pause,
                campaign_set_queue,
            )
        except Exception:
            # We don't want this worker thread to die and block joining
            # at the end of the process.
            traceback.print_exc()

        campaign_set_queue.task_done()


def get_all(queue):
    while True:
        try:
            yield queue.get_nowait()
        except Empty:
            return


def start_workers(num, func, args):
    for i in range(num):
        Thread(target=func, args=args).start()


def collect(client, args):
    customer_id_queue = Queue()
    campaign_set_queue = Queue()

    print('getting customer ids...')
    customer_ids = collect_customer_ids(client)
    print(f'found {len(customer_ids)} customer(s)')

    for customer_id in customer_ids:
        customer_id_queue.put(customer_id)

    print('getting campaign ids...')
    start_workers(
        args.workers,
        retrieve_campaign_ids,
        (client, args.verbose, customer_id_queue, campaign_set_queue),
    )

    customer_id_queue.join()
    campaign_sets = store_campaign_sets(get_all(campaign_set_queue))
    print(f'committed campaign sets {campaign_sets}')

    return campaign_sets


def pause_unpause(client, args, is_pause):
    campaign_sets = args.campaign_sets or collect(client, args)

    print(f'loading campaign sets {campaign_sets}...')
    campaign_set_queue = Queue()
    for campaign_set in load_campaign_sets(campaign_sets):
        campaign_set_queue.put(campaign_set)

    print(f"{'' if is_pause else 'un'}pausing campaigns...")
    start_workers(
        args.workers,
        mutate_worker,
        (client, args.verbose, args.no_dry_run, is_pause, campaign_set_queue),
    )

    campaign_set_queue.join()

    print('done')
    if is_pause:
        print('you can unpause by running')
        print(f'sem-emergency-stop unpause {campaign_sets}')


def pause(client, args):
    return pause_unpause(client, args, True)


def unpause(client, args):
    return pause_unpause(client, args, False)


def setup(client, args):
    print('All set up!')


def parse_arguments(args):
    parser = ArgumentParser(
        formatter_class=RawDescriptionHelpFormatter,
        description=banner + '\n\nEmergency stop for all Google SEM',
    )
    subparsers = parser.add_subparsers(help='sub-command help')

    all_shared = ArgumentParser(add_help=False)
    all_shared.add_argument(
        '--workers',
        help='use NUM workers in parallel',
        type=int,
        metavar='NUM',
        default=16,
    )
    all_shared.add_argument('-v', '--verbose', action='store_true')

    collect_parser = subparsers.add_parser(
        'collect', help='only collect campaign ids', parents=[all_shared]
    )
    collect_parser.set_defaults(func=collect)

    mutation_shared = ArgumentParser(add_help=False)
    mutation_shared.add_argument(
        '--no-dry-run',
        help='actually perform the mutations',
        action='store_true',
    )

    pause_parser = subparsers.add_parser(
        'pause', help='pause campaigns', parents=[all_shared, mutation_shared]
    )
    pause_parser.add_argument(
        'campaign_sets',
        help='use CAMPAIGN-SETS for pausing',
        metavar='CAMPAIGN-SETS',
        nargs='?',
    )
    pause_parser.set_defaults(func=pause)

    unpause_parser = subparsers.add_parser(
        'unpause',
        help='unpause campaigns',
        parents=[all_shared, mutation_shared],
    )
    unpause_parser.add_argument(
        'campaign_sets',
        help='use CAMPAIGN-SETS for unpausing (use the hash from pausing)',
        metavar='CAMPAIGN-SETS',
    )
    unpause_parser.set_defaults(func=unpause)

    setup_parser = subparsers.add_parser(
        'setup', help='set up authentication only', parents=[all_shared]
    )
    setup_parser.set_defaults(func=setup)

    return parser.parse_args(args or ['pause', '--help'])


def run():
    os.makedirs(blob_directory, exist_ok=True)
    args = parse_arguments(sys.argv[1:])
    print(banner)

    credentials = {
        **load_organization_auth(),
        **load_user_auth(),
    }

    client = GoogleAdsClient.load_from_dict(credentials)

    if 'no_dry_run' in args:
        if args.no_dry_run:
            print(
                "\033[31mYou are about to do a non-dry run, please type YOLO:"
            )
            if input('> ') != 'YOLO':
                print('alright, that was close!')
                sys.exit(-1)
        else:
            print('*** THIS IS A DRY RUN ***')
            print('to perform a non-dry run, supply --no-dry-run')

    args.func(client, args)

    if 'no_dry_run' in args and not args.no_dry_run:
        print('*** THIS WAS A DRY RUN ***')
