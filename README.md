# SWAT Tools

## Getting started

The following instructions will walk you through the process of running a local instance of SWAT Tools. Note, the steps are intended to be run in a Linux or macOS environment from a shell.

You must have access to [`docker`](https://docs.docker.com/engine/) and [`docker-compose`](https://docs.docker.com/compose/) before running the steps.

### Setting up the environment files

1. Copy `.env.example` to a new file named `.env`.

   ```
   cp .env.example .env
   ```

2. Provide filepaths for where the Django and Celery logs should be stored on your local machine using the `CELERY_LOGS_DIR` and `DJANGO_LOGS_DIR` environment variables.

   ```
   CELERY_LOG_DIR=/path/for/celery/logs
   DJANGO_LOG_DIR=/path/for/django/logs
   ```

3. Next, enter a user and root password inside `.env` using `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD`.

   ```
   MYSQL_DATABASE=swatapps
   MYSQL_HOST=db
   MYSQL_PASSWORD=mypassword
   MYSQL_PORT=3306
   MYSQL_ROOT_PASSWORD=myrootpassword
   MYSQL_USER=swatapps
   ```

4. Copy `.env.dev.example` to a new file named `.env.dev`.

   ```
   cp .env.dev.example .env.dev
   ```

5. SWAT Tools uses a variety of external resources that are not necessary to run the application locally.

   In `.env.dev`, at a minimum, provide values for the following environment variables:

   ```
   ADMINS=Firstname Lastname,email
   EMAIL_CLIENT_ID=YOUR_GMAIL_CLIENT_ID
   EMAIL_CLIENT_SECRET=YOUR_GMAIL_CLIENT_SECRET
   EMAIL_REFRESH_TOKEN=YOUR_GMAIL_OAUTH2_REFRESH_TOKEN
   SECRET_KEY=mysecretkey
   ```

   Read more about obtaining OAuth 2.0 tokens [here](https://developers.google.com/identity/protocols/oauth2).

   The other variables may be left on their default values and the application will still function. The `AWS_` variables are required if you want to send large uploads to an AWS S3 bucket. The `GTAG_` variables are related to Google Analytics, and the `TURNSTILE_` variables are for enabling Cloudflare Turnstile on the registration page.

### Building and running the Docker containers

1. Before building and running the containers for the first time, you will need to create a Docker network named `swat-tools-net`.

   ```
   docker network create swat-tools-net
   ```

2. Build the docker containers described in `docker-compose.yml` by running:

   ```
   docker-compose build
   ```

   It may take several minutes for this process to finish.

3. Start the containers in the background by running:
   ```
   docker-compose up -d
   ```
