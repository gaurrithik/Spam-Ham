import json
import boto3
import email
import os
from datetime import datetime
import re
from botocore.exceptions import ClientError
import hashlib
import io
import csv
import string
import sys
import numpy as np

from hashlib import md5


if sys.version_info < (3,):
    maketrans = string.maketrans
else:
    maketrans = str.maketrans
    
def vectorize_sequences(sequences, vocabulary_length):
    results = np.zeros((len(sequences), vocabulary_length))
    for i, sequence in enumerate(sequences):
       results[i, sequence] = 1. 
    return results

def one_hot_encode(messages, vocabulary_length):
    data = []
    for msg in messages:
        temp = one_hot(msg, vocabulary_length)
        data.append(temp)
    return data

def text_to_word_sequence(text,filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n',lower=True, split=" "):
    if lower:
        text = text.lower()

    if sys.version_info < (3,):
        if isinstance(text, unicode):
            translate_map = dict((ord(c), unicode(split)) for c in filters)
            text = text.translate(translate_map)
        elif len(split) == 1:
            translate_map = maketrans(filters, split * len(filters))
            text = text.translate(translate_map)
        else:
            for c in filters:
                text = text.replace(c, split)
    else:
        translate_dict = dict((c, split) for c in filters)
        translate_map = maketrans(translate_dict)
        text = text.translate(translate_map)

    seq = text.split(split)
    return [i for i in seq if i]

def one_hot(text, n,filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n',lower=True,split=' '):

    return hashing_trick(text, n, hash_function='md5',filters=filters,lower=lower,split=split)

def hashing_trick(text, n,hash_function=None,filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n',lower=True,split=' '):

    if hash_function is None:
        hash_function = hash
    elif hash_function == 'md5':
        hash_function = lambda w: int(md5(w.encode()).hexdigest(), 16)

    seq = text_to_word_sequence(text,
                                filters=filters,
                                lower=lower,
                                split=split)
    return [int(hash_function(w) % (n - 1) + 1) for w in seq]




# grab environment variables
ENDPOINT_NAME = os.environ['ENDPOINT_NAME']
runtime= boto3.client('runtime.sagemaker')

def send_email(sender,reciever,mail_recieved_at,mail_subject,mail_body,label,score):
    SENDER =  'rl4017@rithik.net' # must be verified in AWS SES Email
    RECIPIENT = 'rl4017@nyu.edu'  # must be verified in AWS SES Email

    # If necessary, replace us-west-2 with the AWS Region you're using for Amazon SES.
    AWS_REGION = "us-east-1"

    # The subject line for the email.
    SUBJECT = "Spam Check Results"

    # The email body for recipients with non-HTML email clients.
    BODY_TEXT = ('We received your email sent at '+ str(mail_recieved_at) +' with the subject ' + str(mail_subject) +'.'+ 
                 '\n Here is a 240 character sample of the email body:\n'+ str(mail_body) 
                 + '\n The email was categorized as '+str(label) +' with a '+ str(score) +'% confidence')
                
    # The HTML body of the email.
    # BODY_HTML = """<html>
    # <head></head>
    # <body>
    # <h1>Hey Hi...</h1>
    # <p>This email was sent with
    #     <a href='https://aws.amazon.com/ses/'>Amazon SES CQPOCS</a> using the
    #     <a href='https://aws.amazon.com/sdk-for-python/'>
    #     AWS SDK for Python (Boto)</a>.</p>
    # </body>
    # </html>
    #             """            

    # The character encoding for the email.
    CHARSET = "UTF-8"

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
            },
            Message={
                'Body': {
                    # 'Html': {
        
                    #     'Data': BODY_HTML
                    # },
                    'Text': {
        
                        'Data': BODY_TEXT
                    },
                },
                'Subject': {

                    'Data': SUBJECT
                },
            },
            Source=SENDER
        )
    # Display an error if something goes wrong.	
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])


def lambda_handler(event, context):
    # TODO implement
    print('process email')
    # Initiate boto3 client
    s3 = boto3.client('s3')
    
    # Get s3 object contents based on bucket name and object key; in bytes and convert to string
    data = s3.get_object(Bucket=event['Records'][0]['s3']['bucket']['name'], Key=event['Records'][0]['s3']['object']['key'])
    contents = data['Body'].read().decode("utf-8")
    
    print('contents:\n',contents)
    # Given the s3 object content is the ses email, get the message content and attachment using email package
    msg = email.message_from_string(contents)
    
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get('Content-Disposition'))

            # skip any text/plain (txt) attachments
            if ctype == 'text/plain' and 'attachment' not in cdispo:
                body = part.get_payload(decode=True)  # decode
                break
    # not multipart - i.e. plain text, no attachments, keeping fingers crossed
    else:
        body = msg.get_payload(decode=True)
    
    
    #strip
    body= body.decode("utf-8")
    body = body.strip()
    
    print('body:\n',body)
    
    # print('subject:\n',msg['Subject'])
    # print('from:\n',msg['From'])
    # print('to:\n',msg['To'])
    # print('date:\n',msg['Date'])
    

    
    
    sender = msg['From']
    reciever = msg['To']
    mail_subject = msg['Subject']
    mail_body = body
    mail_recieved_at=msg['Date']
    
    
    test_messages =[]
    test_messages.append(body)
    
    vocabulary_length = 9013
    
    one_hot_test_messages = one_hot_encode(test_messages, vocabulary_length)
    encoded_test_messages = vectorize_sequences(one_hot_test_messages, vocabulary_length)
    
    data = json.dumps(encoded_test_messages.tolist())
    print(data)
    
    response = runtime.invoke_endpoint(EndpointName=ENDPOINT_NAME,
                                       ContentType='application/json', 
                                       Body=data)
    print(response)

    res = json.loads(response['Body'].read().decode())
    print(res)
    if res['predicted_label'][0][0] == 0:
        label = 'Ham'
    else:
        label = 'Spam'
    score = round(res['predicted_probability'][0][0], 4)
    score = score*100
    
    print(score)
    print(label)
    
    send_email(sender,reciever,mail_recieved_at,mail_subject,mail_body,label,score)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
