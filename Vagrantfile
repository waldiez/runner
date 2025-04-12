# Vagrantfile to spin up multiple Linux VMs for testing the Waldiez Runner setup script
# Includes: Ubuntu, Debian, Fedora, CentOS, Rocky Linux, Arch
# cspell: disable

# not in a release yet, so we patch here till then
# https://github.com/hashicorp/vagrant/pull/13587
# https://github.com/hashicorp/vagrant/issues/13586#issue-2819553197
class VagrantPlugins::ProviderVirtualBox::Model::StorageController
  SCSI_CONTROLLER_TYPES = ["LsiLogic", "BusLogic", "VirtioSCSI"].map(&:freeze).freeze
end

Vagrant.configure("2") do |config|
  config.vm.box_check_update = false

  boxes = [
    { name: "ubuntu", box: "bento/ubuntu-24.04" },
    { name: "debian", box: "bento/debian-12" },
    { name: "fedora", box: "bento/fedora-latest" },
    { name: "centos", box: "bento/centos-stream-10" },
    { name: "rocky", box: "bento/rockylinux-9"},
    { name: "arch", box: "archlinux/archlinux" }
  ]

  boxes.each do |opts|
    config.vm.define opts[:name] do |vm_config|
      vm_name =  "#{opts[:name]}-runner"
      vm_config.vm.box = opts[:box]
      vm_config.vm.hostname = vm_name
        vm_config.vm.disk :disk, size: "100GB", primary: true
      vm_config.vm.provider "virtualbox" do |vb|
        vb.memory = 4096
        vb.cpus = 2
      end
      vm_config.vm.network "private_network", type: "dhcp"
      vm_config.vm.synced_folder ".", "/vagrant", disabled: true

      # On bento/fedora the disc size seems to not be applied, and we might get "no space left"
      if opts[:name] == "fedora" || opts[:name] == "centos" || opts[:name] == "rocky"
        vm_config.vm.provision "shell", inline: <<-SHELL
          set -e
          echo "[*] Rpm family detected — resizing root partition if needed..."
          # Get the device mounted at "/"
          ROOT_DEVICE=$(findmnt -n -o SOURCE /)
          DISK=$(lsblk -no PKNAME "$ROOT_DEVICE" | head -n1)  # parent disk (e.g. sda)
          PART="/dev/$DISK$(echo "$ROOT_DEVICE" | grep -o '[0-9]*$')"  # e.g. /dev/sda3
          DISK="/dev/$DISK"

          echo "[*] Detected root device: $ROOT_DEVICE"
          echo "[*] Parent disk: $DISK"
          echo "[*] Partition to resize: $PART"

          # Install tools
          dnf install -y cloud-utils-growpart util-linux || true

          # Get sizes
          DISK_SIZE=$(lsblk -bndo SIZE "$DISK")
          PART_SIZE=$(lsblk -bndo SIZE "$PART")
          echo "[*] Disk size: $DISK_SIZE"
          echo "[*] Partition size: $PART_SIZE"

          SHOULD_RESIZE=$(awk -v d="$DISK_SIZE" -v p="$PART_SIZE" 'BEGIN { print (p < d) ? 1 : 0 }')

          if [ "$SHOULD_RESIZE" -eq 1 ]; then
            echo "[*] Resizing partition..."
            growpart "$DISK" "$(echo "$PART" | grep -o '[0-9]*$')" || true
            FSTYPE=$(findmnt -n -o FSTYPE /)
            echo "[*] Filesystem type: $FSTYPE"
            case "$FSTYPE" in
              xfs)
                echo "[*] Resizing XFS filesystem..."
                xfs_growfs / || true
                ;;
              ext4)
                echo "[*] Resizing ext4 filesystem..."
                resize2fs "$PART" || true
                ;;
              *)
                echo "[!] Unsupported filesystem: $FSTYPE"
                exit 1
                ;;
            esac
            echo "[+] Resize complete."
          else
            echo "[=] Partition already at full size."
          fi
        SHELL
      end
      vm_config.vm.provision "file", source: "./deploy/compose/do.sh", destination: "/home/vagrant/do.sh"
      vm_config.vm.provision "shell", inline: <<-SHELL
        echo "[#{opts[:name]}] Running setup script..."

        cd /home/vagrant
        DOMAIN_NAME=test.local sh ./do.sh --skip-certbot
        echo "[#{opts[:name]}] Setup complete. Validating..."
        docker info || exit 1
        docker compose -f compose.yaml config || exit 1
        test -f .env && echo ".env exists" || exit 1
      SHELL
    end
  end
end
