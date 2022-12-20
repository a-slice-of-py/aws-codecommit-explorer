import boto3
import streamlit as st

from typing import Sequence
from streamlit_tree_select import tree_select
from streamlit_ace import st_ace, LANGUAGES
from dotenv import load_dotenv
from difflib import get_close_matches
import os

load_dotenv()

st.set_page_config(layout='wide')

if 'client' not in st.session_state:
    st.session_state.client = None
if 'traverse' not in st.session_state:
    st.session_state.traverse = False

def get_folder(repository: str, folder: str) -> dict:
    return st.session_state.client.get_folder(repositoryName=repository, folderPath=folder)

def get_file(repository: str, filepath: str) -> dict:
    return st.session_state.client.get_file(repositoryName=repository, filePath=filepath)

def add_files(response: dict) -> None:
    return [
        {'label': f['relativePath'], 'value': f['absolutePath']}
        for f in response['files']
    ]


def traverse_folder(repository: str, absolute_path: str) -> Sequence:
    response = get_folder(repository, absolute_path)
    files = add_files(response)
    children = []
    for folder in response['subFolders']:
        response = get_folder(repository, folder['absolutePath'])
        children.append(
            {
                'label': folder['relativePath'],
                'value': folder['absolutePath'],
                'children': traverse_folder(repository, folder['absolutePath'])
            }
        )
    children.extend(files)
    return children

@st.experimental_memo
def traverse_repo(repository: str) -> Sequence:
    return [
        {
            'label': repository,
            'value': repository,
            'children': traverse_folder(repository, '/')
        }
    ]

def put_search_interface(nodes: Sequence) -> dict:
    with st.sidebar:
        response = tree_select(nodes, only_leaf_checkboxes=True, check_model='leaf')
    return response

@st.experimental_memo
def list_repositories() -> Sequence:
    response = st.session_state.client.list_repositories(sortBy='repositoryName', order='ascending')
    repos = response['repositories']
    while 'nextToken' in response:
        response = st.session_state.client.list_repositories(nextToken=response['nextToken'], sortBy='repositoryName', order='ascending')
        repos.extend(response['repositories'])
    return repos

def put_form() -> str:
    with st.sidebar.form('Input'):
        default_profile, default_region = os.environ.get('AWS_PROFILE'), os.environ.get('AWS_REGION')
        if default_profile and default_region:
            profile_name, region_name = default_profile, default_region
        else: 
            profile_name = st.text_input(label='AWS Profile')
            region_name = st.text_input(label='AWS Region')
        boto3_session = boto3.Session(profile_name=profile_name, region_name=region_name)
        st.session_state.client = boto3_session.client('codecommit')

        repos = list_repositories()
        selection = st.selectbox(
            label='CodeCommit repo',
            options=repos,
            format_func=lambda x: x['repositoryName']
        )
        if st.form_submit_button('Explore') or st.session_state.traverse:
            st.session_state.traverse = True
            return selection['repositoryName']


def main():
    repository = put_form()
    if repository is not None:
        with st.sidebar:
            nodes = traverse_repo(repository)
            response = put_search_interface(nodes)

        if not response.get('checked'):
            st.stop()
        elif len(response['checked']) > 1:
            st.caption('⚠️ Please select one file at a time.')
        else:
            filename = response['checked'].pop()
            selected_file = get_file(repository, filename)
            content = selected_file['fileContent'].decode('utf-8')
            languages = get_close_matches(filename.split('.')[-1], LANGUAGES, cutoff=0.5)
            st_ace(
                value=content, 
                readonly=True,
                language=languages[0] if languages else 'text',
                theme='tomorrow_night_eighties',
                )

if __name__ == '__main__':
    main()