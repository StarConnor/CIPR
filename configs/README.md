# Configuration

The agent YAML files in this directory are safe to commit and describe agent
workflows. Machine-specific VMware settings belong in `vmware.local.yaml`,
which is intentionally ignored by Git.

For IDE/VM runs:

```bash
cp configs/vmware.example.yaml configs/vmware.local.yaml
# Fill in the local VMX paths, Windows credentials, and SSH settings.
```

Use `VMWARE_CONFIG_PATH` if the local VMware configuration is stored
elsewhere. The IDE YAML files use the `guest.username` value to construct their
Windows paths automatically; no additional environment variables are needed.
