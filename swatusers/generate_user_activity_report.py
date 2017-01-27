from datetime import datetime, timedelta
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
import os
import smtplib
import sys

from mytools import mydatabase

project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.append(project_path + "/swatapps")
os.environ["DJANGO_SETTINGS_MODULES"] = "swatapps"

from settings import EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD


# Establish connection to the database
db = mydatabase.MyDatabase(mycnf="/depot/saraswat/web/swatapps/swatapps/my.cnf")

# Connect to database
db.connect_to_database()

# Get start and end date for query (today plus 1 day minus 7 days)
todays_date = datetime.today()
start_date = datetime.today() - timedelta(days=7)
end_date = datetime.today() + timedelta(days=1)

todays_date_formatted = "%s-%s-%s" % (str(todays_date.year), str(todays_date.month).zfill(2), str(todays_date.day).zfill(2))
start_date_formatted = "%s-%s-%s" % (str(start_date.year), str(start_date.month).zfill(2), str(start_date.day).zfill(2))
end_date_formatted = "%s-%s-%s" % (str(end_date.year), str(end_date.month).zfill(2), str(end_date.day).zfill(2))

# Create query of database for new users in last 7 days
query = "SELECT id FROM `swatusers_swatuser` "
query += "WHERE date_joined BETWEEN "
query += "'%s' AND '%s';" % (start_date_formatted, end_date_formatted)

# Make query on database
query_results = db.query_database(query)

# Fetch records for query to get total of new users this week
new_users_this_week = len(db.fetch_records(query_results, "all"))

# Get date for start of current month
month_date = "%s-%s-01" % (str(todays_date.year), str(start_date.month).zfill(2))

# Create query of data for new users this month
query = "SELECT id FROM `swatusers_swatuser` "
query += "WHERE date_joined BETWEEN "
query += "'%s' AND '%s';" % (todays_date_formatted, month_date)

# Make query on database
query_results = db.query_database(query)

# Fetch records for query to get total of new users this month
new_users_this_month = len(db.fetch_records(query_results, "all"))

# Get date for start of year
year_date = "%s-01-01" % (str(todays_date.year))

# Create query of data for new users this year
query = "SELECT id FROM `swatusers_swatuser` "
query += "WHERE date_joined BETWEEN "
query += "'%s' AND '%s';" % (todays_date_formatted, year_date)

# Make query on database
query_results = db.query_database(query)

# Fetch records for query to get total of new users this year
new_users_this_year = len(db.fetch_records(query_results, "all"))

# Email summary
email_summary_msg = "-" * 47
email_summary_msg += "\nSWAT Tools new user summary\n"
email_summary_msg += "-" * 47
email_summary_msg += "\nLast Week (%s - %s):\t%s" % (start_date_formatted, todays_date_formatted, str(new_users_this_week))
email_summary_msg += "\nCurrent Month (%s-%s):\t\t\t%s" % (str(todays_date.year), str(todays_date.month).zfill(2), str(new_users_this_month))
email_summary_msg += "\nCurrent Year (%s):\t\t\t\t%s\n" % (str(todays_date.year), str(new_users_this_year))
email_summary_msg += "-" * 47

# Construct MIME obj
msg = MIMEMultipart()
msg["From"] = EMAIL_HOST_USER
msg["To"] = "hancocb@purdue.edu"
msg["Subject"] = "Weekly SWAT Tools user report"
msg.attach(MIMEText(email_summary_msg, "plain"))

# Connect to email server, construct message elements, and send
email_server = smtplib.SMTP(EMAIL_HOST)
email_server.starttls()
email_server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
email_server.sendmail(EMAIL_HOST_USER, "hancocb@purdue.edu", msg.as_string())
email_server.quit()
