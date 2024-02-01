# Checkinarator Visualizer 

Simple chart generator which displays checkins by those in the challenges

## Secrets

In order to access the data in the database `DB_CONNECT_STRING` needs to be set.
This value is stored in a [sops](https://github.com/getsops/sops) encrypted `.env`
file and can be encrypted and decrypted using the scripts in `./scripts` assuming
you have access to an allowed key.
