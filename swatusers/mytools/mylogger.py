import logging


class MyLogger():
    """ Creates logger for script. """

    def __init__(self, logpath=""):
        
        # if logpath provided
        if logpath:
            # Instantiate logger and set level to INFO
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)

            # Specify logging to file rather than stream and set level to DEBUG
            handler = logging.FileHandler(logpath)
            handler.setLevel(logging.DEBUG)

            # Set format for logging
            formatter = logging.Formatter("%(asctime)s - %(levelname)s -%(message)s")
            handler.setFormatter(formatter)

            # Add formatted file handler to main logger
            self.logger.addHandler(handler)
