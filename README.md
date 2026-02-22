# Ansible Collection Role Fixer - Docker Container

Kubespray to galaxy convertor

## What It Does

The kubespray current design is not Galaxy friendly. 
This container will change the code in kubespray to solved this.

Changes are only done on strict role and playbook naming, documentation and code clenaup prio to import.

### Run

```bash
docker run --rm -t \
    -e GALAXY_URL="https://galaxy.ansible.com/api/" \
    -e GALAXY_TOKEN="<YOUR GALAXY TOKEN>" \
    -e KUBESPRAY_VERSION="<KUBESPRAY VERSION>" \
    localhost/collection_fixer
```

## License

Apache License 2.0
