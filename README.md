# Ansible Collection Role Fixer - Docker Container

Kubespray to galaxy collection convertor

## What It Does

The kubespray current design is not Galaxy friendly. 
This container will change the code in kubespray to solved this.

Changes will be done only on:
    - strict role naming
    - strict playbook naming
    - documentation
    - remove files not needed in a collection

## Run

Optain your ```<YOUR GALAXY TOKEN>``` and determin the ```<KUBESPRAY VERSION>```

```bash
docker run --rm -t \
    -e GALAXY_URL="https://galaxy.ansible.com/api/" \
    -e GALAXY_TOKEN="<YOUR GALAXY TOKEN>" \
    -e KUBESPRAY_VERSION="<KUBESPRAY VERSION>" \
    vdveldet/kubespray-collection-fixer:latest
```

## License

Apache License 2.0

export GALAXY_URL="https://galaxy.ansible.com/api/"
export GALAXY_TOKEN=""
export KUBESPRAY_VERSION=""

docker run --rm -t \
    -e GALAXY_URL="${GALAXY_URL}" \
    -e GALAXY_TOKEN="${GALAXY_TOKEN}" \
    -e KUBESPRAY_VERSION="${KUBESPRAY_VERSION}" \
    vdveldet/kubespray-collection-fixer:latest