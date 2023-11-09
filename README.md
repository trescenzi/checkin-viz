# Checkinarator Visualizer 

Simple chart generator which displays checkins by those in the challenges

## Secrets

In order to access the data in the google sheet `$GOOGLE_API_KEY` needs to be set.
This value is stored in a sops encrypted `.env` file and can be encrypted and decrypted
using the scripts in `./scripts` assuming you have access to an allowed key.
