# Route to check the permission

[
  {
    "section": "ticket",
    "permission": "view",
    "allowed": true
  },
  {
    "section": "ticket",
    "permission": "assign",
    "allowed": true
  },
  {
    "section": "leave",
    "permission": "edit",
    "allowed": false
  },
  {
    "section": "salary",
    "permission": "view",
    "allowed": true
  },
  {
    "section": "project",
    "permission": "edit",
    "allowed": true
  }
]


# Route to check the permission

def get_authorized_superadmin(required_section=None, required_permissions=None):
    userID = g.user.get('userID') if g.user else None
    if not userID:
        return None, jsonify({"status": "error", "message": "No auth token"}), 401

    superadmin = SuperAdmin.query.filter_by(id=userID).first()
    if superadmin:
        return superadmin, None, None

    user = User.query.filter_by(id=userID).first()
    if not user:
        return None, jsonify({"status": "error", "message": "Unauthorized user"}), 403

    if required_section and required_permissions:
        if isinstance(required_permissions, str):
            required_permissions = [required_permissions]

        matched_permission = next((
            access for access in user.access_permissions
            if access.section == required_section.lower()
            and access.permission in [perm.lower() for perm in required_permissions]
            and access.allowed
        ), None)

        if not matched_permission:
            return None, jsonify({
                "status": "error",
                "message": f"Access denied for '{required_section}' section with required permission(s): {required_permissions}"
            }), 403

    superadmin = SuperAdmin.query.filter_by(superId=user.superadminId).first()
    if not superadmin:
        return None, jsonify({"status": "error", "message": "No superadmin found"}), 404

    return superadmin, None, None
