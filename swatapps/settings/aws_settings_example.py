# AWS access keys
AWS_ACCESS_KEY_ID = ""
AWS_SECRET_ACCESS_KEY = ""

# S3 bucket name
AWS_STORAGE_BUCKET_NAME = ""

# S3 bucket region
S3DIRECT_REGION = ""

# File destinations based on type
S3DIRECT_DESTINATIONS = {
    "misc": {
        "key": '/',
        "auth": lambda u: u.is_authenticated(),
        "allowed": [],
        "content_length_range": (1, 25000)  # bytes
    }
}