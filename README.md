# sem-emergency-stop

![Logo](doc/sem-emergency-stop.svg)

Stop all Google Ads marketing. This utility will pause all marketing campaigns on Google Ads (presumably across many accounts) as fast as possible. The main use case is emergency response during incidents where all landing pages are temporarily unavailable, thereby incurring cost without revenue. Unpausing the paused campaigns (and only those) is also supported.


## Usage

In case of emergency, do this:

```shell
sem-emergency-stop pause --no-dry-run
```

A hash will be printed at the end of the process. Use this hash to unpause when the incident is over (the exact instructions are displayed when you run.)


## One-time setup (for end users)

Install the tool (requires Python 3.7 or higher; on Ubuntu 18.04 install `python3.7-minimal`):

```shell
pip3 install --user sem-emergency-stop
```

You can then run `sem-emergency-stop setup` to authenticate the tool against the API using your Google account. This will request two pieces of information from you:

 1. An organization token. How you get this token depends on your organization's process. See the next section if you are the person to set this up for your organization.
 2. A token specific to your Google account. Follow instructions on screen. Note that you need to have access to your Ads accounts with your Google account.


## Deployment at organizations

Authentication uses Google's OAuth2 flow. This app does _not_ come with client secrets, so you will have to generate these and distribute them in your organization through a suitable channel (e.g. using password manager). The client id/secret together with your login customer id and your developer token are packaged in a compact _organization token_ for distribution purposes.

After installing the app, you can generate a token by running `ses-create-org-token`. It will ask the following information:

 * Login customer id - this is the customer id (without dashes) of your root Google Ads account.
 * Developer token - find it in your root account under "API Center".
 * Client id/secret - follow [this guide](https://developers.google.com/google-ads/api/docs/oauth/cloud-project) how to obtain a pair.


## Development and contributing

For development [pipenv](https://pipenv.kennethreitz.org/en/latest/) is required on your system. Set up the development environment with `make develop`, run with `pipenv run sem-emergency-stop ...` as needed.

We welcome pull requests; if you are planning to perform bigger changes then it makes sense to file an issue first. Make sure `make lint` comes back clean.


## Security

For sensitive security matters please contact [security@getyourguide.com](mailto:security@getyourguide.com).


## Legal

Copyright 2021 GetYourGuide GmbH.

sem-emergency-stop is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for the full text.
