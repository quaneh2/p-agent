# Notes

## Phase 1
Phase 1 is just around setting up a service that will poll it's own email inbox looking for emails, and send and automated reply when it receives one.

First I set up the gmail and google cloud accounts for the Agent
Saved credentials in the project.
Wrote a gitignore so that I can make my repo without exposing creds.
Added my module requirements for using google apis
Created a venv to keep things clean

Wrote agent.py file to authenticate w/ Gmail API
Agent polls the email inbox for up to 10 emails
Agent extracts email details (sender body etc.)
Agent replies in the same thread
Agent only processes emails from whitelisted senders

GOOGLE SHUT DOWN MY ACCOUNT
I needed to create a new user under my google workspace instead.
Have now set it up under poolbeg solutions account and downloaded new creds
This time we made our client only accessible by "Internal" i.e. accounts within our workspace
We ran authentication to get our token.json file.... SUCCESS

Next I'm going to deploy to Render. I'll make sure the deployment process is working smoothly and test email receival and sending after deployment again. Then I'll add some real "agent" functionality

Our client will need to get the Gmail API token from env vars in Render now.



