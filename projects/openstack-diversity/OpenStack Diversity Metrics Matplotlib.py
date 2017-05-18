# coding: utf-8
#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#     Daniel Izquierdo <dizquierdo@bitergia.com>
#




import matplotlib
import numpy as np
import matplotlib.pyplot as plt

from datetime import datetime

import pandas

from util import ESConnection
from elasticsearch_dsl import Search, Q

es_conn = ESConnection()




# ## Basic metrics to be in the report:
# 
# **Git**
# * Evolution and trends over time [per quarter] of commits by gender
#   * Commits by gender (columns: hash, gender)
# * Evolution and trends [per quarter] of developers over time by gender
#   * Developers by gender (columns: name, uuid, gender)
# * Evolution and trends of type of contributions (code or others) by gender over time
#   * Type of file touched by developers (columns: filetype, gender)
# 
# **Gerrit**
# * Evolution of code reviews over time by gender
#   * Count votes by gender (vote, gender)
# * Evolution of code reviews developers over time by gender
#   * Count people voting (name, uuid, vote)
# * Evolution of core reviews over time by gender
#   * Votes +2 or -2 (vote +2/-2 and gender)
# * Evolution of core review developers over time by gender
#   * People voting +2 or -2 (name, uuid, vote +2/-2, gender)
# 
# **Others**
# * Evolution of attracted developers over time by gender
#   * First commit by gender
# * Time working in the community by gender
#   * Time difference between the first and last contribution by all developers (so how long developers remain in OpenStack?).

# # SOME FUNCTIONS

# In[407]:

def evol_chart(title, x_data, y_data, y_legend, file_name):
    ''' Save evolutionary charts in line format

    :param title: chart title
    :param x_data: values in X
    :param y_data: list of lists containing the values to display in Y
    :param y_legend: list of values with the legend of Y values
    :param file_name: file name

    :type title: string
    :type x_data: list of datetime strings that follow the format %Y-%m-%dT
    :type y_data: list of lists of values
    :type y_legend: list of strings. As many as lists in y_data
    :type file_name: string
    '''

    fig = plt.figure()

    plt.title(title)

    dates = []
    for unixdate in x_data:
        date = unixdate.split("T")[0]
        dates.append(datetime.strptime(date, "%Y-%m-%d"))

    for y in y_data:
        plt.plot(dates, y)

    fig.autofmt_xdate()

    # loc = 2 => legend is displayed at the top left side of the chart
    plt.legend(y_legend, loc=2)
    #plt.show()

    fig.savefig("/tmp/" + file_name)

    plt.close()


def pie_chart(title, labels, fractions, file_name):
    ''' Build and save pie chart

    :param title: title of the chart
    :param labels: list of labels
    :param fractions: list of percentages to be represented
    :param file_name: name of the file used to save

    :type title: string
    :type labels: list of strings
    :type fractions: list of floats
    :type file_name: string
    '''

    fig = plt.figure(1, figsize=(8,8))
    ax = plt.axes([0.1, 0.1, 0.8, 0.8])

    plt.pie(fractions, labels=labels, autopct='%1.1f%%', startangle=90)

    plt.title(title)
    fig.savefig("/tmp/" + file_name)

    plt.close()


def project_list(index):
    s = Search(using=es_conn, index=index)
    s.aggs.bucket('projects', 'terms', field='projects', size=700)
    result = s.execute()

    value = result.to_dict()["aggregations"]["projects"]["buckets"]
    df = pandas.DataFrame()
    df2 = pandas.DataFrame()
    for i in value:
        df2["project"] = [i["key"]]
        df = pandas.concat([df, df2])

    return list(df["project"])


def query_metric_over_time(index, metric_name, metric_field, filters = []):

    s = Search(using=es_conn, index=index)  # Index selection
    for filtering in filters:
        s = s.filter(filtering)
    s.aggs.bucket('time', 'date_histogram', field='date', interval='quarter', min_doc_count=0) \
          .bucket('gender', 'terms', field='gender', min_doc_count=0) \
          .metric(metric_name, 'cardinality', field=metric_field, precision_threshold=10000)
    result = s.execute()

    value = result.to_dict()["aggregations"]['time']['buckets']
    df = pandas.DataFrame()
    for i in value:
        df2 = (pandas.DataFrame.from_dict(i["gender"]["buckets"]))
        df2["time"] = datetime.fromtimestamp(i["key"]/1000).strftime("%Y-%m-%d")
        try:
            df2[metric_name] = df2[metric_name].apply(lambda row:row["value"])
        except:
            print ("ERROR FOUND!")
            df2[metric_name] = 0
        df = pandas.concat([df, df2])
    df["gender"] = df["key"]
    df["key_as_string"] = df["time"]
    return df


def query_total_changesets(index, metric_name, metric_field, filters = []):
    s = Search(using=es_conn, index=index)  # Index selection
    for filtering in filters:
        s = s.filter(filtering)
    #s = s.filter('range', date={'gt': start_date, 'lt':'now/M'}) # filter date
    s.aggs.bucket('gender', 'terms', field='gender')          .metric(metric_name, 'cardinality', field=metric_field, precision_threshold=10000)
    result = s.execute()

    buckets = result.to_dict()["aggregations"]["gender"]["buckets"]
    pie_chart_labels = []
    pie_chart_values = []
    for bucket in buckets:
        pie_chart_labels.append(bucket["key"])
        pie_chart_values.append(bucket[metric_name]["value"])

    return pie_chart_labels, pie_chart_values


# # GERRIT

def gerrit_info(project):
    #filter_project = Q('term', projects=project)
    #project_name = project
    project_name = ""
    filter_project = Q()

    INDEX = "gerrit_eventized"
    filter_date_4y = Q('range', date={'gt': 'now/M-4y', 'lt':'now/M'})
    filter_date_1y = Q('range', date={'gt': 'now/M-1y', 'lt':'now/M'})


    # ## Changeset Submissions by Gender
    # 
    # ### Evolution of submissions sent over time by gender
    # 

    METRIC_NAME = "changesets"
    METRIC_FIELD = "id"
    df = query_metric_over_time(INDEX, METRIC_NAME, METRIC_FIELD, [filter_date_4y, filter_project])


    chart_title = "Changeset Submissions by Gender"
    x_data = df[df["gender"]=="female"]["key_as_string"]
    y_data = [df[df["gender"]=="male"][METRIC_NAME],
              df[df["gender"]=="female"][METRIC_NAME],
              df[df["gender"]=="NotKnown"][METRIC_NAME]]
    y_legend = ["male", "female", "Unknown"]
    file_name = project_name + "openstack_changeset_submissions_by_gender"

    evol_chart(chart_title, x_data, y_data, y_legend, file_name)


# ### Aggregated changeset submissions by gender

    pie_chart_labels, pie_chart_values = query_total_changesets(INDEX, METRIC_NAME, METRIC_FIELD, [filter_date_4y, filter_project])

    total = np.array(pie_chart_values).sum()
    values = list((np.array(pie_chart_values) / total ) * 100)
    title = "Changeset Submissions by Gender (last 4 years)"
    pie_chart(title, pie_chart_labels, values, project_name + "openstack_piechart_changeset_submissions_by_gender_4y")


    pie_chart_labels, pie_chart_values = query_total_changesets(INDEX, METRIC_NAME, METRIC_FIELD, [filter_date_1y, filter_project])

    total = np.array(pie_chart_values).sum()
    values = list((np.array(pie_chart_values) / total ) * 100)
    title = "Changeset Submissions by Gender (last year)"
    pie_chart(title, pie_chart_labels, values, project_name + "openstack_piechart_changeset_submissions_by_gender_1y")


# ## Population of people submitting changesets
# ### Evolution of submitters over time by gender
#   * Count people submitting (id, uuid)

    METRIC_NAME = "submitters"
    METRIC_FIELD = "uuid"
    df = query_metric_over_time(INDEX, METRIC_NAME, METRIC_FIELD, [filter_date_4y, filter_project])

    chart_title = "Changeset submitters by gender"
    x_data = df[df["gender"]=="female"]["key_as_string"]
    y_data = [df[df["gender"]=="male"][METRIC_NAME],
              df[df["gender"]=="female"][METRIC_NAME],
              df[df["gender"]=="NotKnown"][METRIC_NAME]]
    y_legend = ["male", "female", "Unknown"]
    file_name = project_name + "openstack_changeset_submitters_by_gender"

    evol_chart(chart_title, x_data, y_data, y_legend, file_name)


# ### Aggregated number of submitters
# 

    pie_chart_labels, pie_chart_values = query_total_changesets(INDEX, METRIC_NAME, METRIC_FIELD, [filter_date_4y, filter_project])
    total = np.array(pie_chart_values).sum()
    values = list((np.array(pie_chart_values) / total ) * 100)
    title = "Developers submitting changesets by Gender (last 4 years)"
    pie_chart(title, pie_chart_labels, values, project_name + "openstack_piechart_changeset_submitters_by_gender_4y")


# * Evolution of code reviews developers over time by gender
#   * Count people voting (name, uuid, vote)
# 

    pie_chart_labels, pie_chart_values = query_total_changesets(INDEX, METRIC_NAME, METRIC_FIELD,  [filter_date_1y, filter_project])
    total = np.array(pie_chart_values).sum()
    values = list((np.array(pie_chart_values) / total ) * 100)
    title = "Developers submitting changesets by Gender (last year)"
    pie_chart(title, pie_chart_labels, values, project_name + "openstack_piechart_changeset_submitters_by_gender_1y")


# ## Number of votes by gender

    METRIC_NAME = "reviewer"
    METRIC_FIELD = "uuid"
    filter_vote = Q('term', eventtype='CHANGESET_PATCHSET_APPROVAL_Code-Review') # filter by event: vote a code review

    df = query_metric_over_time(INDEX, METRIC_NAME, METRIC_FIELD, [filter_date_4y, filter_vote, filter_project])


# In[423]:

    chart_title = "Code review votes by gender"
    x_data = df[df["gender"]=="female"]["key_as_string"]
    y_data = [df[df["gender"]=="male"]["doc_count"],
              df[df["gender"]=="female"]["doc_count"],
              df[df["gender"]=="NotKnown"]["doc_count"]]
    y_legend = ["male", "female", "Unknown"]
    file_name = project_name + "openstack_code_review_votes_by_gender"

    evol_chart(chart_title, x_data, y_data, y_legend, file_name)


# ## Number of people voting

# In[424]:

    chart_title = "Code reviewers voting by gender"
    x_data = df[df["gender"]=="female"]["key_as_string"]
    y_data = [df[df["gender"]=="male"][METRIC_NAME],
              df[df["gender"]=="female"][METRIC_NAME],
              df[df["gender"]=="NotKnown"][METRIC_NAME]]
    y_legend = ["male", "female", "Unknown"]
    file_name = project_name + "openstack_code_reviewers_voting_by_gender"

    evol_chart(chart_title, x_data, y_data, y_legend, file_name)


# ## Number of core reviews (-2 OR +2) by gender

# In[425]:

    METRIC_NAME = "core_reviewers"
    METRIC_FIELD = "uuid"

    filter_core_vote = Q('terms', value=["2", "-2"])
    filter_vote = Q('term', eventtype='CHANGESET_PATCHSET_APPROVAL_Code-Review') # filter by event: vote a code review
    df = query_metric_over_time(INDEX, METRIC_NAME, METRIC_FIELD, [filter_core_vote, filter_date_4y, filter_vote, filter_project])


# In[426]:

    chart_title = "Core code reviewes by gender"
    x_data = df[df["gender"]=="female"]["key_as_string"]
    y_data = [df[df["gender"]=="male"]["doc_count"],
              df[df["gender"]=="female"]["doc_count"],
              df[df["gender"]=="NotKnown"]["doc_count"]]
    y_legend = ["male", "female", "Unknown"]
    file_name = project_name + "openstack_core_code_reviews_by_gender"

    evol_chart(chart_title, x_data, y_data, y_legend, file_name)


# ## Number of people acting as core reviews (-2 OR +2) by gender

# In[427]:

    chart_title = "Core code reviewers voting by gender"
    x_data = df[df["gender"]=="female"]["key_as_string"]
    y_data = [df[df["gender"]=="male"][METRIC_NAME],
              df[df["gender"]=="female"][METRIC_NAME],
              df[df["gender"]=="NotKnown"][METRIC_NAME]]
    y_legend = ["male", "female", "Unknown"]
    file_name = project_name + "openstack_core_code_reviewers_voting_by_gender"

    evol_chart(chart_title, x_data, y_data, y_legend, file_name)


# # GIT

def git_info(project):
# In[446]:
    filter_date_4y = Q('range', date={'gt': 'now/M-4y', 'lt':'now/M'})
    filter_date_1y = Q('range', date={'gt': 'now/M-1y', 'lt':'now/M'})


    #project_name = project
    #filter_project = Q('term', projects=project)
    project_name = ""
    filter_project = Q()


    INDEX = "git_eventized"
    filter_merges_addedlines = Q('range', addedlines={'gt': 0})
    filter_merges_removedlines = Q('range', removedlines={'gt': 0})
    filter_bots = Q('bool', must_not=[Q('match', gender_analyzed_name='Jenkins')])


# ## Evolution and trends over time [per quarter] of commits by gender
#   * Commits by gender (columns: hash, gender)

# In[447]:

    METRIC_NAME = "commits"
    METRIC_FIELD = "id.keyword"
    df = query_metric_over_time(INDEX, METRIC_NAME, METRIC_FIELD, [filter_date_4y, filter_merges_addedlines,
                                                                   filter_merges_removedlines, filter_bots,
                                                                   filter_project])

# In[448]:
    chart_title = "Commits by gender"
    x_data = df[df["gender"]=="female"]["key_as_string"]
    y_data = [df[df["gender"]=="male"][METRIC_NAME],
              df[df["gender"]=="female"][METRIC_NAME],
              df[df["gender"]=="NotKnown"][METRIC_NAME]]
    y_legend = ["male", "female", "Unknown"]
    file_name = project_name + "openstack_commits_by_gender"

    evol_chart(chart_title, x_data, y_data, y_legend, file_name)


# In[449]:

    pie_chart_labels, pie_chart_values = query_total_changesets(INDEX, METRIC_NAME, METRIC_FIELD,
                                                                [filter_date_4y, filter_merges_addedlines,
                                                                 filter_merges_removedlines, filter_bots,
                                                                 filter_project])
    total = np.array(pie_chart_values).sum()
    values = list((np.array(pie_chart_values) / total ) * 100)
    title = "Commits by Gender (last 4 years)"
    pie_chart(title, pie_chart_labels, values, project_name + "openstack_piechart_commits_by_gender_4years")


# In[450]:

    pie_chart_labels, pie_chart_values = query_total_changesets(INDEX, METRIC_NAME, METRIC_FIELD,
                                                                [filter_date_1y, filter_merges_addedlines,
                                                                 filter_merges_removedlines, filter_bots,
                                                                 filter_project])
    total = np.array(pie_chart_values).sum()
    values = list((np.array(pie_chart_values) / total ) * 100)
    title = "Commits by Gender (last year)"
    pie_chart(title, pie_chart_labels, values, project_name + "openstack_piechart_commits_by_gender_1year")


# 
# ## Evolution and trends [per quarter] of developers over time by gender
#   * Developers by gender (columns: name, uuid, gender)

# In[431]:

    METRIC_NAME = "authors"
    METRIC_FIELD = "uuid"
    filter_merges_addedlines = Q('range', addedlines={'gt': 0})
    filter_merges_removedlines = Q('range', removedlines={'gt': 0})
    filter_bots = Q('bool', must_not=[Q('match', gender_analyzed_name='Jenkins')])
    df = query_metric_over_time(INDEX, METRIC_NAME, METRIC_FIELD, [filter_date_4y, filter_merges_addedlines,
                                                                   filter_merges_removedlines, filter_bots,
                                                                   filter_project])



# In[432]:

    chart_title = "Developers submitting commits"
    x_data = df[df["gender"]=="female"]["key_as_string"]
    y_data = [df[df["gender"]=="male"][METRIC_NAME],
              df[df["gender"]=="female"][METRIC_NAME],
              df[df["gender"]=="NotKnown"][METRIC_NAME]]
    y_legend = ["male", "female", "Unknown"]
    file_name = project_name + "openstack_developers_submitting_commits_by_gender"

    evol_chart(chart_title, x_data, y_data, y_legend, file_name)


# In[452]:

    pie_chart_labels, pie_chart_values = query_total_changesets(INDEX, METRIC_NAME, METRIC_FIELD,
                                                                [filter_date_4y, filter_merges_addedlines,
                                                                 filter_merges_removedlines, filter_bots,
                                                                 filter_project])
    total = np.array(pie_chart_values).sum()
    values = list((np.array(pie_chart_values) / total ) * 100)
    title = "Developers committing changes by Gender (last 4 years)"
    pie_chart(title, pie_chart_labels, values, project_name + "openstack_piechart_developers_submitting_commits_by_gender_4years")


# In[454]:

    pie_chart_labels, pie_chart_values = query_total_changesets(INDEX, METRIC_NAME, METRIC_FIELD,
                                                                [filter_date_1y, filter_merges_addedlines,
                                                                 filter_merges_removedlines, filter_bots,
                                                                 filter_project])
    total = np.array(pie_chart_values).sum()
    values = list((np.array(pie_chart_values) / total ) * 100)
    title = "Developers committing changes by Gender (last years)"
    pie_chart(title, pie_chart_labels, values, project_name + "openstack_piechart_developers_submitting_commits_by_gender_1year")


# ## Evolution and trends of type of contributions (code or others) by gender over time
#   * Type of file touched by developers (columns: filetype, gender)


# In[433]:

    METRIC_NAME = "code_files_touched"
    METRIC_FIELD = "id.keyword"
    filter_merges_addedlines = Q('range', addedlines={'gt': 0})
    filter_merges_removedlines = Q('range', removedlines={'gt': 0})
    filter_bots = Q('bool', must_not=[Q('match', gender_analyzed_name='Jenkins')])
    filter_filetype = Q('term', filetype='code')
    df = query_metric_over_time(INDEX, METRIC_NAME, METRIC_FIELD, [filter_date_4y, filter_merges_addedlines,
                                                                   filter_merges_removedlines, filter_bots,
                                                                   filter_filetype, filter_project])



# In[434]:

    chart_title = "Code files touched by gender"
    x_data = df[df["gender"]=="female"]["key_as_string"]
    y_data = [df[df["gender"]=="male"]["doc_count"],
              df[df["gender"]=="female"]["doc_count"],
              df[df["gender"]=="NotKnown"]["doc_count"]]
    y_legend = ["male", "female", "Unknown"]
    file_name = project_name + "openstack_code_files_touched_by_gender"

    evol_chart(chart_title, x_data, y_data, y_legend, file_name)


# In[435]:

    METRIC_NAME = "others_files_touched"
    METRIC_FIELD = "id.keyword"
    filter_merges_addedlines = Q('range', addedlines={'gt': 0})
    filter_merges_removedlines = Q('range', removedlines={'gt': 0})
    filter_bots = Q('bool', must_not=[Q('match', gender_analyzed_name='Jenkins')])
    filter_filetype = Q('term', filetype='other')
    df = query_metric_over_time(INDEX, METRIC_NAME, METRIC_FIELD, [filter_date_4y, filter_merges_addedlines,
                                                                   filter_merges_removedlines, filter_bots,
                                                                   filter_filetype, filter_project])



# In[436]:

    chart_title = "Non code files touched by gender"
    x_data = df[df["gender"]=="female"]["key_as_string"]
    y_data = [df[df["gender"]=="male"]["doc_count"],
              df[df["gender"]=="female"]["doc_count"],
              df[df["gender"]=="NotKnown"]["doc_count"]]
    y_legend = ["male", "female", "Unknown"]
    file_name = project_name + "openstack_non_code_files_touched_by_gender"

    evol_chart(chart_title, x_data, y_data, y_legend, file_name)



def main():
   for project in project_list('gerrit_eventized'):
       if project == 'Unknown':
           continue
       print (project)
       git_info(project)
       print ("git info ready to go")
       gerrit_info(project)
       print ("gerrit info ready to go")

       break

if __name__== '__main__':
    main()
