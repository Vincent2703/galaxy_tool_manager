from galaxy.schema.fields import Security
from galaxy.webapps.galaxy.services.base import ServiceBase


class OsugGroupsService(ServiceBase):
    def get_current_user_groups(self, trans):
        groups = [
            {
                "id": Security.security.encode_id(group_association.group.id), #To get the encoded id
                "name": group_association.group.name
            }
            for group_association in trans.user.groups 
            if group_association.group.deleted == 0
        ]

        return groups