#!/usr/bin/env python3
"""Consulta só metadados de GitHub Actions para diagnosticar deploys recentes.

Requer GITHUB_TOKEN de leitura/actions:read do próprio workflow.
Não expõe token e não altera nuvem, secrets ou branch.
"""
import json
import os
from urllib import parse, request


def api(path):
    token = os.environ["GITHUB_TOKEN"]
    url = "https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"] + path
    req = request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


for workflow in ("deploy-services.yml", "deploy-hosting.yml", "deploy-scriptorium-alias.yml"):
    q = parse.urlencode({"branch": "main", "per_page": "3"})
    data = api("/actions/workflows/" + workflow + "/runs?" + q)
    print("WORKFLOW: " + workflow)
    for run in data.get("workflow_runs", [])[:3]:
        print("  id={} SHA={} status={} conclusion={} update={}".format(
            run.get("id"), (run.get("head_sha") or "")[:12],
            run.get("status"), run.get("conclusion"), run.get("updated_at")))
        if run.get("status") == "completed" and run.get("conclusion") not in ("success",):
            jobs = api("/actions/runs/{}/jobs?per_page=15".format(run["id"]))
            for job in jobs.get("jobs", []):
                print("  JOB id={} name={} conclusion={}".format(
                    job.get("id"), job.get("name"), job.get("conclusion")))
                for step in job.get("steps", []):
                    if step.get("conclusion") == "failure":
                        print("    FALHA na etapa: " + str(step.get("name")))
