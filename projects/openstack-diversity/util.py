
import certifi
import configparser

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search

def ESConnection():

    parser = configparser.ConfigParser()
    parser.read('.settings')

    section = parser['ElasticSearch']
    user = section['user']
    password = section['password']
    host = section['host']
    port = section['port']
    path = section['path']

    connection = "https://" + user + ":" + password + "@" + host + ":" + port + "/" + path

    es_read = Elasticsearch([connection], use_ssl=True, verity_certs=True, ca_cert=certifi.where(), scroll='300m', timeout=200)

    return es_read

def test():
    es_conn = ESConnection()

    s = Search(using=es_conn, index='git')
    s.execute()

    for item in s.scan():
        print(item)
        break

if __name__ == "__main__":
    test()
