import json
import boto3
from botocore.exceptions import ClientError
from botocore.vendored import requests
import os

###################################################################
# generate an access token to access the Strava API
###################################################################
def get_access_token() :
    # OAuth: get a token. make sure you did the manual steps explained above, in order to get a code.
    # Client id and client secret are obtained when creating a strava app. That's the first step (manual)
    oauth_endpoint = 'https://www.strava.com/oauth/token'
    client_id = os.environ['CLIENT_ID']
    client_secret = os.environ['CLIENT_SECRET']
    code = os.environ['CODE']
    oauth_parameters = {
            "client_id": client_id, 
            "client_secret": client_secret, 
            "code": code
        }
    
    oauth_response = requests.post(oauth_endpoint, params = oauth_parameters)
    if oauth_response.status_code != 200:
        raise Exception("OAuth response was not successful")
        
    response_content = json.loads(oauth_response.content.decode("utf-8"))
    access_token = response_content['access_token']
    return access_token

###################################################################
# Given an activity id, it gets information about the activity
# This includes:
# 'name' - name of the activity
# 'external_id' - name of the original fit file uploaded to Strava
###################################################################
def get_activity_info(id, token) :
    url_endpoint = 'https://www.strava.com/api/v3'
    url_what = '/activities/' + str(id)  

    headers = {"Authorization": "Bearer " + token}
    
    activities_response = requests.get(url_endpoint + url_what, headers=headers)
    if activities_response.status_code != 200:
        raise Exception("Could not access the activity info")

    info = json.loads(activities_response.content.decode("utf-8"))
    return info

###################################################################
# Given an file (filename) containing the template for the email
# body (containing the fields {ulr}, {current_activity_name},
# {activity_id}, and {external_id}), returns the text with the
# fields replaced.
###################################################################
def read_email_text(filename, url, current_activity_name, activity_id, external_id) :
    body_str = ""
    with open(filename, encoding='utf8') as f:
        body_str = f.read().strip()
    body = body_str
    return body.format(url=url, current_activity_name=current_activity_name, activity_id=activity_id, external_id=external_id)
      

#####################################
####       Lambda function       ####
#####################################
def lambda_handler(event, context):

    bucket_name = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    # Create a presigned download url that will expire in 2 days
    s3Client = boto3.client('s3')
    params = {'Bucket': bucket_name, 'Key': key}
    expire_in_hours = 48
    seconds_in_one_hour = 60
    expire_in_seconds = expire_in_hours * seconds_in_one_hour
    url = s3Client.generate_presigned_url('get_object', Params = params, ExpiresIn = expire_in_seconds)
    
    # Get information about the activity
    # Since the original fit file was downloaded, its name may have changed. For this reason,
    # We'll ping the Strava API to get the current ride name. It is not guaranteed to be the final name,
    # but we have a better chance this way.
    external_id = ""
    activity_id = ""
    ride_original_name = ""
    try:
        metadata = s3Client.head_object(Bucket=bucket_name, Key=key)
        ride_original_name = metadata['ResponseMetadata']['HTTPHeaders']['x-amz-meta-original_name']
        activity_id = metadata['ResponseMetadata']['HTTPHeaders']['x-amz-meta-activity_id']
        external_id = metadata['ResponseMetadata']['HTTPHeaders']['x-amz-meta-external_id']
        print("Metadata: activity name = " + ride_original_name)
        print("Metadata: activity id = " + activity_id)
        print("Metadata: name of original fit file uploaded = " + external_id)
    except Exception as e:
        print(e)
    
    access_token = get_access_token()
    info = get_activity_info(activity_id, access_token)
    current_activity_name = info['name']
    if current_activity_name != ride_original_name :
        print("The name of the activity has changed since its original file was downloaded")
        print("Name at time of download: " + ride_original_name)
        print("Current name: " + current_activity_name)
    else:
        print("The name of the activity has NOT changed since its original file was downloaded")
    
    ###############  Prepare email content #################
    # These addresses must be verified with Amazon SES.
    SENDER = os.environ['SENDER']
    RECIPIENT = os.environ['RECIPIENT_EMAIL']
    CC_RECIPIENT = os.environ['CC_EMAIL']

    # AWS Region you're using for Amazon SES.
    AWS_REGION = "eu-west-1"

    # The subject line for the email.
    SUBJECT = os.environ['EMAIL_SUBJECT']
    
    # The character encoding for the email.
    CHARSET = "UTF-8"
    
    # The HTML body of the email.
    # The html text is in a dedicated file, containing the variables indicated below
    BODY_HTML = read_email_text('html_body.txt', url, current_activity_name, activity_id, external_id)

    # The email body for recipients with non-HTML email clients.
    # The text is in a dedicated file, containing the variables indicated below
    BODY_TEXT = read_email_text('text_body.txt', url, current_activity_name, activity_id, external_id)


    ################## email content ready #######################
    
    # Create a new SES resource and specify a region.
    client = boto3.client('ses',region_name=AWS_REGION)

    # Try to send the email.
    try:
        #Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
                'CcAddresses': [
                    CC_RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': BODY_HTML,
                    },
                    'Text': {
                        'Charset': CHARSET,
                        'Data': BODY_TEXT,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
        )
    # Display an error if something goes wrong.	
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])

