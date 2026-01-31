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
We've successfully deployed on Render. I tested that it's working.
Strangely there were no logs. Found out I need and the -u flag to the run command so that the output is unbuffered.

Ok, now time to actually add an AI agent. I've created a new anthropic API key.
I've added anthropic to my reqs, not to update the agent.py file
I'm starting with my system prompt and I'm trying to give it a bit of personality. 
I've based it on Mr. Stevens, the butler from Remains of the Day. I'm thinking I'm going to use this as a writing agent, but I'm not really thinking about that too much yet.. just want a bit of personlity for the initial phase.

Added init_claude function. 
Looks for API key. Throws error if not found.

Updated process_email function
Instead of just creating a reply, it now creates a prompt based on the email received, and makes an api call to claude with the system prompt and this new user prompt.

Also made sure init_claude is called in run_agent after authenticating the gmail api.



