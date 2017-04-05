import MySQLdb

from .mylogger import MyLogger


class MyDatabase():
    """ Connects to database and handles query requests. """

    def __init__(self, mycnf=""):
        """ Initialize MyDatabase object. """

        # Path to MySQL configuration file
        self.config = mycnf

        # Database connection and location within database
        self.dbconn = None
        self.cursor = None

        # Set up logger
        self.logger = MyLogger(logpath="/depot/saraswat/web/swatapps/swatapps/log/cron/user_activity_log.log").logger

    def connect_to_database(self):
        """ Connect to the database provided in MySQL config file. """

        self.dbconn = MySQLdb.connect(
            read_default_file=self.config)

    def disconnect_from_database(self):
        """ Close connection to the database. """

        self.dbconn.close()

    def query_database(self, query=""):
        """ Query database with provided query and return result. """

        if query:
            try:
                # Try to set cursor and execute query
                self.cursor = self.dbconn.cursor()
                result = self.cursor.execute(query)
            except:
                result = ""
                self.logger.info("Unable to find cursor or execute query.")
        else:
            result = ""

        return result

    def fetch_records(self, query_results, fetch_type="all", n=0):
        """ Collect rows found by query. Three methods: fetch one record 
            ("one"), fetch a specific number of records ("many" and n), or
            fetch all records ("all"). """

        # Fetch records based on fetch_type
        if fetch_type == "one":
            records = self.cursor.fetchone()
        elif fetch_type == "all":
            records = self.cursor.fetchall()
        elif fetch_type == "many":
            records = self.cursor.fetchmany(n)
        else:
            records = None

        return records

    def delete_records(self, query=""):
        """ Removes records from database. """

        try:
            # Find records and remove.
            self.query_database(query)
            self.commit_change()
        except:
            self.logger.info("Unable to delete records in database.")

    def commit_change(self):
        """ Finalizes changes to the database (e.g. deletions). """

        self.dbconn.commit()
