# Strava Send Email

AWS Lambda function that is triggered by a new file being uploaded to a specific folder in the S3 bucket. It composes an email containing a signed url to the new file, and sends it using SES.

The new file is a fixed `.fit` file corresponding to an activity in Strava. Since the name of the activity may have changed since the original (unfixed) file was downloaded, this function uses the Strava API to query the current name of the activity.
