# ── EFS Filesystem ─────────────────────────────────────────────────────────────
#
# EFS provides the shared ReadWriteMany volumes needed by:
#   - git-repos PVC  (git-service writes bare repos; api/worker read them)
#   - nginx-apps PVC (worker writes per-app .conf files; nginx-apps pod reads them)
#
# In Phase 1 this replaces the host-path bind-mounts in docker-compose.yml.

resource "aws_security_group" "efs" {
  name        = "${var.cluster_name}-efs"
  description = "Allow NFS (TCP 2049) from EKS nodes"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.eks_nodes.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.cluster_name}-efs"
  }
}

resource "aws_efs_file_system" "main" {
  creation_token  = "${var.cluster_name}-efs"
  encrypted       = true

  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  tags = {
    Name = "${var.cluster_name}-efs"
  }
}

# One mount target per private subnet (two AZs)
resource "aws_efs_mount_target" "private" {
  count = length(module.vpc.private_subnets)

  file_system_id  = aws_efs_file_system.main.id
  subnet_id       = module.vpc.private_subnets[count.index]
  security_groups = [aws_security_group.efs.id]
}

# ── EFS Access Points ──────────────────────────────────────────────────────────
#
# Separate access points keep the git-repos and nginx-apps data in distinct
# root directories on the same filesystem. The EFS CSI dynamic provisioner
# will use these when the StorageClass is configured with the access point ID.
#
# Note: in this Phase 1 setup the PVCs are statically provisioned (the
# volumeHandle in the PV references the filesystem ID directly). Access points
# are created here for Phase 2 when dynamic provisioning is wired up.

resource "aws_efs_access_point" "git_repos" {
  file_system_id = aws_efs_file_system.main.id

  root_directory {
    path = "/git-repos"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "755"
    }
  }

  tags = {
    Name = "${var.cluster_name}-efs-git-repos"
  }
}

resource "aws_efs_access_point" "nginx_apps" {
  file_system_id = aws_efs_file_system.main.id

  root_directory {
    path = "/nginx-apps"
    creation_info {
      owner_gid   = 101  # nginx group
      owner_uid   = 101  # nginx user
      permissions = "755"
    }
  }

  tags = {
    Name = "${var.cluster_name}-efs-nginx-apps"
  }
}
