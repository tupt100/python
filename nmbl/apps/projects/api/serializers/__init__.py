from .attachments import (  # noqa
    AttachmentBasicSerializer,
    AttachmentCreateSerializer,
    AttachmentDetailsSerializer,
    AttachmentListSerializer,
    AttachmentPrimaryKeyRelatedField,
    AttachmentSerializer,
    AttachmentUpdateSerializer,
    DocumentBaseSerializer,
    DocumentBasicSerializer,
    DocumentDetailsSerializer,
)
from .projects import *  # noqa
from .servicedesks import (  # noqa
    RequestTaskListSerializer,
    ServiceDeskRequestBasicSerializer,
    ServiceDeskRequestSerializer,
    ServiceDeskUserBasicSerializer,
)
from .tags import TagBasicSerializer, TagSerializer  # noqa
from .tasks import *  # noqa
from .templates import *  # noqa
from .users import UserBasicSerializer, UserSerializer  # noqa
from .workflows import *  # noqa
from .workgroups import (  # noqa
    CompanyWorkGroupBasicSerializer,
    CompanyWorkGroupDetailSerializer,
    UserWorkGroupListSerializer,
    WorkGroupAddMemberSerializer,
    WorkGroupDetailSerializer,
    WorkGroupListSerializer,
    WorkGroupMemberCreateSerializer,
    WorkGroupProjectSerializer,
    WorkGroupRemoveMemberSerializer,
    WorkGroupTaskSerializer,
    WorkGroupUpdateSerializer,
    WorkGroupWorkflowSerializer,
)
