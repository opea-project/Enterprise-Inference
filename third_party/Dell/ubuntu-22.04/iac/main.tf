terraform {
  required_providers {
    redfish = {
      source  = "dell/redfish"
      version = "1.6.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

provider "redfish" {
  redfish_servers = {
    server1 = {
      user         = var.idrac_user
      password     = var.idrac_password
      endpoint     = var.idrac_endpoint
      ssl_insecure = var.idrac_ssl_insecure
    }
  }
}

resource "redfish_boot_source_override" "boot_from_virtual_media" {
  redfish_server {
    redfish_alias = "server1"
  }
  
  system_id = "System.Embedded.1"
  
  boot_source_override_enabled = "Once"
  boot_source_override_target  = "Cd"
  # boot_source_override_mode not supported on 17G servers
  # Note: reset_type is required but may not always trigger reboot reliably
  # The redfish_power resource below ensures the reboot happens
  reset_type = "ForceRestart"
  
  lifecycle {
    # Allow the resource to be replaced/updated when configuration changes
    create_before_destroy = false
  }
}

# Wait a few seconds after boot override is set to ensure ISO is ready
# This also acts as a trigger to force the power resource to apply
# To force a reboot, change any value in the triggers (e.g., add a comment with timestamp)
resource "null_resource" "boot_override_trigger" {
  depends_on = [redfish_boot_source_override.boot_from_virtual_media]
  
  provisioner "local-exec" {
    command = "echo 'Waiting 5 seconds for ISO to be fully ready before reboot...' && sleep 5"
  }
  
  triggers = {
    boot_target = redfish_boot_source_override.boot_from_virtual_media.boot_source_override_target
    boot_enabled = redfish_boot_source_override.boot_from_virtual_media.boot_source_override_enabled
    boot_override_id = redfish_boot_source_override.boot_from_virtual_media.id
    # To force reboot: uncomment and change the timestamp below, or run: terraform taint redfish_power.reboot_for_install
    # force_reboot = "2024-01-01T00:00:00Z"
  }
}

resource "redfish_power" "reboot_for_install" {
  redfish_server {
    redfish_alias = "server1"
  }
  
  system_id = "System.Embedded.1"
  
  desired_power_action = "ForceRestart"
  maximum_wait_time    = 120
  
  depends_on = [
    redfish_boot_source_override.boot_from_virtual_media,
    null_resource.boot_override_trigger
  ]
  
  lifecycle {
    # Force replacement when boot override changes to ensure reboot is applied
    replace_triggered_by = [
      null_resource.boot_override_trigger
    ]
  }
}

output "installation_ready" {
  value = {
    boot_configured      = redfish_boot_source_override.boot_from_virtual_media.boot_source_override_target == "Cd"
    boot_override_type   = redfish_boot_source_override.boot_from_virtual_media.boot_source_override_enabled
    boot_target          = redfish_boot_source_override.boot_from_virtual_media.boot_source_override_target
    iso_url              = "https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso"
    ready_to_reboot      = redfish_boot_source_override.boot_from_virtual_media.boot_source_override_target == "Cd"
    note                 = "Run ./mount-iso.sh before terraform apply. Boot mode (UEFI/Legacy) not configurable via Terraform on 17G servers."
  }
  description = "Ubuntu installation readiness status"
}

output "installation_config" {
  value = {
    username  = var.ubuntu_username
    hostname  = var.ubuntu_hostname
    use_dhcp  = var.use_dhcp
    static_ip = var.use_dhcp ? "N/A (DHCP)" : var.static_ip
  }
  description = "Ubuntu installation configuration (password is sensitive)"
}

output "verification_commands" {
  value = {
    check_hostname = "curl -sk -u <idrac_user>:<idrac_password> ${var.idrac_endpoint}/redfish/v1/Systems/System.Embedded.1 | jq -r '.HostName'"
    check_boot     = "curl -sk -u <idrac_user>:<idrac_password> ${var.idrac_endpoint}/redfish/v1/Systems/System.Embedded.1/Boot | jq -r '.BootSourceOverrideEnabled'"
    idrac_console  = "${var.idrac_endpoint} (login: <idrac_user>/<idrac_password>, then open Virtual Console)"
    mount_iso_script = "./mount-iso.sh"
    run_script        = "./verify-installation.sh"
  }
  description = "Commands and methods to verify Ubuntu installation (replace <idrac_user> and <idrac_password> with actual values)"
}
