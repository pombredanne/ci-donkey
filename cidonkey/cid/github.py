import requests
import json


def process_github_webhook(request, build_info):
    """
    extracts the required data about the event from
    a request object resulting from a webhook request.
    """
    rjson = request.get_json()
    secret = request.headers.get('X-Hub-Signature')
    if secret != build_info.project.webhook_secret:
        return 403, 'permission denied'
    build_info.trigger = request.headers.get('X-GitHub-Event')
    private = None
    if build_info.trigger not in build_info.project.webhooks:
        return False, '"%s" is not an allowed webhook.' % build_info.trigger
    if build_info.trigger == 'push':
        build_info.author = rjson['pusher']['name']
        # TODO if head_commit = None return not building
        build_info.commit_message = rjson['head_commit']['message']
        build_info.display_url = rjson['head_commit']['url']
        default_branch = rjson['repository']['default_branch']
        build_info.sha = rjson['head_commit']['id']
        build_info.label = rjson['ref']
        build_info.status_url = rjson['repository']['statuses_url']\
                .replace('{sha}',build_info.sha)
        build_info.on_master = build_info.label.endswith(default_branch)
        private = rjson['repository']['private']
    elif build_info.trigger == 'pull_request':
        build_info.author = rjson['sender']['login']
        build_info.commit_message = rjson['pull_request']['title']
        build_info.display_url = rjson['pull_request']['_links']['html']['href']
        private = rjson['pull_request']['head']['repo']['private']
        build_info.sha = rjson['pull_request']['head']['sha']
        build_info.action = rjson['action']
        if build_info.action == 'closed':
            return 200, 'not running ci when pull request is closed'
        build_info.label = rjson['pull_request']['head']['label']
        build_info.status_url = rjson['pull_request']['statuses_url']
        build_info.fetch_cmd = 'pull/%(number)d/head:pr_%(number)d' % rjson
        build_info.fetch_branch = 'pr_%(number)d' % rjson
        build_info.on_master = False
    if build_info.project.private != private:
        print 'changing project private status to %r' % private
        build_info.project.private = private
        build_info.project.save()
    statues, _ = github_api(build_info.status_url, build_info.project.github_token)
    if len(statues) > 0 and not build_info.project.allow_repeat:
        return 200, 'not running ci, status already exists for this commit'
    build_info.save()
    return 202, build_info


def github_api(url, token, method=requests.get, data=None):
    headers = {'Authorization': 'token %s' % token}
    payload = None
    if data:
        payload = json.dumps(data)
    r = method(url, data=payload, headers=headers)
    try:
        return json.loads(r.text), r
    except ValueError:
        return None, r