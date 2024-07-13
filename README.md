# Checkinarator Visualizer 

Simple chart generator which displays checkins by those in the challenges

## Running the App

This app is dockerized and can be both run locally or as a container.

### Dependencies

This app uses poetry for dependency managment.
[Install poetry following the instructions on their site](https://github.com/python-poetry/poetry) 
and then run `poetry install`. From there use `poetry shell` and then the entrypoint with `python src/main.py`.

### Secrets

In order to access the data in the database `DB_CONNECT_STRING` needs to be set.
This value is stored in a [sops](https://github.com/getsops/sops) encrypted `.env`
file and can be encrypted and decrypted using the scripts in `./scripts` assuming
you have access to an allowed key. Before you can access these secrets you'll have to 
generate a new [age key pair](https://github.com/FiloSottile/age) and provide your public
key to someone who already has access. Once they resign the secrete with your public key
you'll be able to decrypt using the decrypt script.
