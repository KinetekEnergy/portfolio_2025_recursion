import json
import requests
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

def get_token_dotenv():
    """Retrieve the GitHub token from environment variables."""
    return os.getenv('GITHUB_TOKEN')

# Correcting the get_token_aws function to properly parse the JSON response
def get_token_aws():
    api_endpoint = 'https://7vybv54v24.execute-api.us-east-2.amazonaws.com/GithubSecret'
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(api_endpoint, headers=headers)
        if response.status_code == 200:
            # Assuming the API returns a JSON object with the token in a field named 'token'
            return response.json().get('token')
        else:
            print("Request failed with status code:", response.status_code)
            print("Response:", response.text)
    except Exception as e:
        print("Error:", str(e))
        return None
    
def get_github_token():
    """
    Attempts to retrieve the GitHub token first from environment variables.
    If not found, it falls back to retrieving the token from AWS.
    """
    # Attempt to get the token from .env
    token = get_token_dotenv()
    
    # If the token is not found in .env, attempt to get it from AWS
    if not token:
        print("Token not found in .env, attempting to retrieve from AWS...")
        token = get_token_aws()
        
        # Ensure the token received from AWS is valid
        if not token:
            print("Failed to retrieve token from AWS.")
            return None
    
    return token

def get_target_info():
    """Retrieve the target type and name from environment variables."""
    return os.getenv('GITHUB_TARGET_TYPE'), os.getenv('GITHUB_TARGET_NAME')

def test_token(token):
    """Test the GitHub token by fetching the current user's profile."""
    response = requests.get('https://api.github.com/user', headers={'Authorization': f'token {token}'})
    if response.status_code == 200:
        print("Token is valid.")
        return True
    else:
        print("Token is invalid or expired.")
        return False
    
def list_org_repos(token, org_name):
    """List all repositories for a given organization."""
    url = f'https://api.github.com/orgs/{org_name}/repos'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()  # List of repositories
    else:
        print(f"Failed to list repositories for {org_name}, Status Code: {response.status_code}")
        return None

def fetch_profile(token, target_type, target_name):
    """Fetch profile information of a specified organization or user."""
    if target_type == 'organization':
        url = f'https://api.github.com/orgs/{target_name}'
    elif target_type == 'user':
        url = f'https://api.github.com/users/{target_name}'
    else:
        print("Invalid target type. Use 'organization' or 'user'.")
        return None

    response = requests.get(url, headers={'Authorization': f'token {token}'})
    if response.status_code == 200:
        return response.json()
    else:
        # Parse the JSON response body to extract the error message
        error_message = json.loads(response.text).get('message', 'Failed to fetch data')
        print(f"Failed to fetch data: {error_message}, status: {response.status_code}")
        return None
    
def list_org_projects(token, org_name):
    """Fetch all projects for a given organization, handling pagination."""
    projects = []
    url = f'https://api.github.com/orgs/{org_name}/projects'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.inertia-preview+json'
    }
    
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            projects.extend(response.json())
            # Check if there is a 'next' page
            if 'next' in response.links:
                url = response.links['next']['url']
            else:
                url = None
        else:
            print(f"Failed to fetch projects, status code: {response.status_code}")
            break

    return projects

def list_org_projects_v2(token, org_login):
    """Fetch all projectsV2 for a given organization, handling pagination with GraphQL."""
    projects = []
    graphql_url = 'https://api.github.com/graphql'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    query = """
    query($orgLogin: String!, $cursor: String) {
      organization(login: $orgLogin) {
        projectsV2(first: 100, after: $cursor) {
          edges {
            node {
              id
              title
              url
            }
          }
          pageInfo {
            endCursor
            hasNextPage
          }
        }
      }
    }
    """
    variables = {'orgLogin': org_login, 'cursor': None}

    while True:
        response = requests.post(graphql_url, headers=headers, json={'query': query, 'variables': variables})
        if response.status_code == 200:
            data = response.json()['data']['organization']['projectsV2']
            projects.extend([edge['node'] for edge in data['edges']])
            if data['pageInfo']['hasNextPage']:
                variables['cursor'] = data['pageInfo']['endCursor']
            else:
                break
        else:
            print(f"Failed to fetch projectsV2, status code: {response.status_code}")
            break

    return projects

def list_org_projects_v2_with_issues(token, org_login):
    '''Fetch all projectsV2 for a given organization, including issues for each project.'''
    projects_with_issues = []
    graphql_url = 'https://api.github.com/graphql'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    query = """
    query($orgLogin: String!, $cursor: String) {
    organization(login: $orgLogin) {
        projectsV2(first: 10, after: $cursor) {
        edges {
            node {
            id
            title
            url
            items(first: 100) {
                nodes {
                id
                ... on ProjectV2Item {
                    type
                    content {
                    ... on Issue {
                        id
                        title
                        url
                        body
                        projectItems(first: 10){
                        nodes{
                            fieldValues(first:10){
                            nodes{
                                ... on ProjectV2ItemFieldTextValue{
                                   text 
                                }
                                ... on ProjectV2ItemFieldNumberValue{
                                   number 
                                }
                                ... on ProjectV2ItemFieldDateValue{
                                   date 
                                }
                            }
                            }
                        }
                    }
                    }
                    }
                }
                }
            }
            }
        }
        pageInfo {
            endCursor
            hasNextPage
        }
        }
    }
    }
    """
    variables = {'orgLogin': org_login, 'cursor': None}

    while True:
        response = requests.post(graphql_url, headers=headers, json={'query': query, 'variables': variables})
        response_json = response.json()
        if response.status_code == 200:
            if 'errors' in response_json:
                print(f"Error in GraphQL query: {response_json['errors']}")
                break
            data = response_json.get('data', {}).get('organization', {}).get('projectsV2', None)
            if data is None:
                print("No projectsV2 data found.")
                break
            for edge in data['edges']:
                project = edge['node']
                
                # Adjusted filtering logic to account for nested structure
                issues = [{
                    'id': item['content']['id'],
                    'title': item['content']['title'],
                    'url': item['content']['url'],
                    'body': item['content']['body'],
                    'fields': item['content']['projectItems']['nodes'][0]['fieldValues']['nodes']
                } for item in project['items']['nodes'] if item['type'] == 'ISSUE']
                if issues:  # Check if there are any issues
                    projects_with_issues.append({
                        'id': project['id'],
                        'title': project['title'],
                        'url': project['url'],
                        'issues': issues
                    })
            if not data['pageInfo']['hasNextPage']:
                break
            variables['cursor'] = data['pageInfo']['endCursor']
        else:
            print(f"Failed to fetch projectsV2 with issues, status code: {response.status_code}, response: {response_json}")
            break

    return projects_with_issues

def get_project_issues_as_dict(token, target_name, selected_project_title):
    '''Retrieve the issues for a specific project as a dictionary.'''
    projects_with_issues = list_org_projects_v2_with_issues(token, target_name)
    selected_project = next((project for project in projects_with_issues if project['title'] == selected_project_title), None)
    project_data = {}

    if selected_project:
        project_data['title'] = selected_project['title']
        project_data['issues'] = []
        if 'issues' in selected_project and selected_project['issues']:
            for issue in selected_project['issues']:
                issue_data = {
                    'title': issue['title'],
                    'url': issue['url'],
                    'start_week': next((int(field['number']) for field in issue['fields'] if 'number' in field), 'N/A'),
                    'start_date': next((field['date'] for field in issue['fields'] if 'date' in field), 'N/A'),
                    'end_date': next((field['date'] for field in issue['fields'] if 'date' in field and field['date'] != project_data['issues'][-1]['start_date']), 'N/A'),
                    'body': issue['body']
                }
                project_data['issues'].append(issue_data)
        else:
            project_data['error'] = "No issues found for this project."
    else:
        project_data['error'] = "Project not found."

    return project_data

def get_project_issues_as_dict(token, target_name, selected_project_title):
    projects_with_issues = list_org_projects_v2_with_issues(token, target_name)
    selected_project = next((project for project in projects_with_issues if project['title'] == selected_project_title), None)
    project_data = {}

    if selected_project:
        project_data['title'] = selected_project['title']
        project_data['issues'] = []
        if 'issues' in selected_project and selected_project['issues']:
            for issue in selected_project['issues']:
                date_fields = [field['date'] for field in issue['fields'] if 'date' in field]
                issue_data = {
                    'title': issue['title'],
                    'url': issue['url'],
                    'start_week': next((str(int(field['number'])) for field in issue['fields'] if 'number' in field), 'N/A'),
                    'start_date': date_fields[0] if date_fields else 'N/A',
                    'end_date': date_fields[1] if len(date_fields) > 1 else 'N/A',
                    'body': issue['body']
                }
                project_data['issues'].append(issue_data)
        else:
            project_data['error'] = "No issues found for this project."
    else:
        project_data['error'] = "Project not found."

    return project_data


if __name__ == "__main__":
    # Main function to test the GitHub API functions
    
    ''' Development Testing: 
    # ENV files allow for easy reuse, changing of tokens and target names
    # Example .env file:
    GITHUB_TOKEN=ghp_1234567890abcdefgh # GitHub Personal Access Token, obtain through GitHub Developer Settings
    GITHUB_TARGET_TYPE=organization  # Use 'organization' or 'user', some items only work for organizations
    GITHUB_TARGET_NAME=nighthawkcoders # This is a GitHub organization example
    '''

    # Initialize primary data variables 
    profile = None # User or organization profile
    projects = None # List of projects
   
    # Retrieve and validate the token
    token = get_github_token()
    target_type, target_name = get_target_info()
    if token and test_token(token): # Token is valid
        # Test GitHub API with the token, returns the name of the GitHub organization or user 
        profile = fetch_profile(token, target_type, target_name)
        if profile:
            print(f"{target_type.capitalize()} Profile:", profile['name'])
        else:
            print("Could not retrieve profile.")
    else:
        print("Exiting due to invalid token.")
        
    # List all repositories for organization or user
    repos = list_org_repos(token, target_name)
    if repos:
        print(f"Repositories for {target_name}:")
        for repo in repos:
            print(f"- {repo['name']}: {repo['html_url']}")
    else:
        print("Could not retrieve repositories.")
        
        
    ''' Organization-specific functions 
    List all repositories, projects, and issues for a given organizationi
    '''
    if profile and target_type == 'organization':
        # List all projects for the organization, V1 project only    
        projects = list_org_projects(token, target_name)
        if projects:
            print(f"Projects V1 for {target_name}:")
            for project in projects:
                print(f"- {project['name']}: {project['html_url']}")
        else:
            print("Could not retrieve projects.")
        
        # List all projects for the organization, V2 projects
        projectsV2 = list_org_projects_v2(token, target_name)
        if projectsV2:
            print(f"Projects V2 for {target_name}:")
            for project in projectsV2:
                print(f"- {project['title']}: {project['url']}")
        else:
            print("Could not retrieve projects.")
           
        # Obtain a specific project and its issues   
        selected_project_title = "CSSE 1-2,  2025"
        project_issues = get_project_issues_as_dict(token, target_name, selected_project_title)
        print()
        print(f"Issues for project {project_issues['title']}:")
        for issue in project_issues['issues']:
            print("---")
            print(f"- {issue['title']}, {issue['url']}")
            print(f"Start Week: {issue['start_week']}")
            print(f"Start Date: {issue['start_date']}")
            print(f"End Date: {issue['end_date']}")
            print(f"{issue['body']}")
            print("---")
            