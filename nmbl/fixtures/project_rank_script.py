from authentication.models import User
from projects.models import (Task, TaskRank, Project, ProjectRank, Workflow,
                             WorkflowRank)

TaskRank.truncate()
ProjectRank.truncate()
WorkflowRank.truncate()
for user in User.objects.all().exclude(company=None):
    company = user.company
    print(user, company)
    for task in Task.objects.filter(organization=company):
        print(task)
        TaskRank.objects.create(user=user, task=task, rank=task.id)
    for project in Project.objects.filter(organization=company):
        print(project)
        ProjectRank.objects.create(user=user, project=project, rank=project.id)
    for workflow in Workflow.objects.filter(organization=company):
        print(workflow)
        WorkflowRank.objects.create(user=user, workflow=workflow,
                                    rank=workflow.id)
