from mwviews.api import PageviewsClient
from datetime import date
import json
import boto3
import os

aws_access_key_id = os.getenv("AWS_ACCESS_KEY")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS")
aws_bucket='doordash-mockup-daniel'
aws_folder = 'wikipedia-batch/raw'
processing_date = date.today().strftime("%Y-%m-%d")
aws_file = aws_folder + '/processing_date=' + processing_date + '/data.json'


s3 = boto3.resource(
    's3',
    region_name='us-east-2',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key
)

p = PageviewsClient(user_agent="<daniel.tanaka@poatek.com>")
domains_list = [
    "meta.wikimedia",
    "io.wiktionary",
    "pl.wiktionary",
    "az.wikipedia",
    "en.wikisource",
    "fi.wikipedia",
    "ka.wikipedia",
    "th.wikipedia",
    "pl.wikipedia",
    "en.wiktionary",
    "vi.wikipedia",
    "azb.wikipedia",
    "incubator.wikimedia",
    "tr.wikipedia",
    "en.wikibooks",
    "sr.wikipedia",
    "el.wiktionary",
    "it.wikipedia",
    "hi.wikipedia",
    "nl.wikipedia",
    "eo.wikipedia",
    "az.wikiquote",
    "no.wikipedia",
    "rue.wikipedia",
    "es.wikipedia",
    "ko.wikipedia",
    "bn.wikipedia",
    "fr.wikipedia",
    "ja.wikipedia",
    "fr.wiktionary",
    "zh.wikipedia",
    "de.wikipedia",
    "ca.wikipedia",
    "he.wikipedia",
    "lv.wikipedia",
    "uk.wikisource",
    "fa.wikipedia",
    "ar.wikipedia",
    "bg.wikipedia",
    "ru.wikipedia",
    "uk.wikipedia",
    "id.wikipedia",
    "pt.wikipedia",
    "sk.wikipedia",
    "cs.wikipedia",
    "en.wikipedia",
    "sv.wikipedia",
    "commons.wikimedia"]

project_views = p.project_views(domains_list)
project_views_keys_str = {}
data_list = []
for key in project_views:
    new_key = key.strftime("%Y-%m-%d")
    project_views_keys_str[new_key] = project_views[key]

for date in project_views_keys_str:
    for key in project_views_keys_str[date]:
        data_dict = {
            "date": date,
            "domain": key,
            "pageviews": project_views_keys_str[date][key]
        }
        data_list.append(data_dict)

with open("/tmp/wikipedia-data.json", "w") as outfile:
    outfile.write(json.dumps(data_list, indent=4))

s3.Bucket(aws_bucket).upload_file('/tmp/wikipedia-data.json', aws_file)