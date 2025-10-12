"""
tigris_bucket_creator.py - Standalone script to create a bucket in Tigris Storage
"""

import logging
import os

import boto3
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def create_tigris_bucket():
    """Create a bucket in Tigris Storage"""
    # Get credentials and settings from environment
    bucket_name = os.environ.get("S3_BUCKET_NAME")
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL_S3")
    region = os.environ.get("AWS_REGION", "us-east-1")

    if not bucket_name:
        logger.error("S3_BUCKET_NAME environment variable is not set")
        return False

    if not endpoint_url:
        logger.error("AWS_ENDPOINT_URL_S3 environment variable is not set")
        return False

    logger.info(f"Attempting to create bucket '{bucket_name}' in Tigris Storage")

    try:
        # Create S3 client
        s3 = boto3.client("s3", endpoint_url=endpoint_url)

        # Check if bucket already exists
        try:
            s3.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket '{bucket_name}' already exists")
            return True
        except Exception as e:
            logger.info(f"Bucket '{bucket_name}' doesn't exist: {e}")

            # Try to create the bucket - different methods
            try:
                # Method 1: Standard create_bucket with no parameters
                logger.info("Attempting to create bucket with standard parameters")
                s3.create_bucket(Bucket=bucket_name)
                logger.info(f"Successfully created bucket '{bucket_name}'")
                return True
            except Exception as e1:
                logger.warning(f"Standard create failed: {e1}")

                try:
                    # Method 2: With LocationConstraint
                    logger.info(
                        f"Attempting to create bucket with LocationConstraint={region}"
                    )
                    s3.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={"LocationConstraint": region},
                    )
                    logger.info(
                        f"Successfully created bucket '{bucket_name}' with region constraint"
                    )
                    return True
                except Exception as e2:
                    logger.warning(f"LocationConstraint create failed: {e2}")

                    try:
                        # Method 3: With empty CreateBucketConfiguration
                        logger.info(
                            "Attempting to create bucket with empty configuration"
                        )
                        s3.create_bucket(
                            Bucket=bucket_name, CreateBucketConfiguration={}
                        )
                        logger.info(
                            f"Successfully created bucket '{bucket_name}' with empty config"
                        )
                        return True
                    except Exception as e3:
                        logger.error(
                            f"All bucket creation methods failed. Last error: {e3}"
                        )
                        return False

    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}")
        return False


if __name__ == "__main__":
    if create_tigris_bucket():
        print("Bucket created or already exists successfully!")
    else:
        print("Failed to create bucket. Check logs for details.")
