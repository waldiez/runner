# Vagrantfile to spin up multiple Linux VMs for testing the Waldiez Runner setup script
# Includes: Ubuntu, Debian, Fedora, CentOS, Rocky Linux, Arch

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
      vm_config.vm.box = opts[:box]
      vm_config.vm.hostname = "#{opts[:name]}-runner"
      vm_config.vm.disk :disk, size: "100GB", primary: true
      vm_config.vm.provider "virtualbox" do |vb|
        vb.memory = 4096
        vb.cpus = 2
      end

      vm_config.vm.network "private_network", type: "dhcp"
      vm_config.vm.synced_folder ".", "/vagrant", disabled: true
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
