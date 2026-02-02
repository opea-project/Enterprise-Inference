variable "ubuntu_username" {
  description = "Username for the default Ubuntu user"
  type        = string
  default     = "ubuntu"
}

variable "ubuntu_password" {
  description = "Password for the default Ubuntu user"
  type        = string
  sensitive   = true
  default     = "ChangeMe123!"
}

variable "ubuntu_hostname" {
  description = "Hostname for the Ubuntu system"
  type        = string
  default     = "ubuntu-server"
}

variable "ssh_keys" {
  description = "SSH public keys to add to the default user (optional, one per line)"
  type        = list(string)
  default     = []
}

variable "use_dhcp" {
  description = "Use DHCP for network configuration (true) or static IP (false)"
  type        = bool
  default     = true
}

variable "static_ip" {
  description = "Static IP address (required if use_dhcp = false)"
  type        = string
  default     = ""
}

variable "static_netmask" {
  description = "Subnet mask in CIDR notation (e.g., 24 for 255.255.255.0)"
  type        = string
  default     = "24"
}

variable "static_gateway" {
  description = "Default gateway (required if use_dhcp = false)"
  type        = string
  default     = ""
}

variable "static_dns" {
  description = "DNS servers (list)"
  type        = list(string)
  default     = ["8.8.8.8", "8.8.4.4"]
}

variable "idrac_endpoint" {
  description = "iDRAC Redfish endpoint URL (e.g., https://100.67.153.16). Can also be set via TF_VAR_idrac_endpoint environment variable."
  type        = string
  default     = "https://100.67.153.16"
}

variable "idrac_user" {
  description = "iDRAC username. Can also be set via TF_VAR_idrac_user environment variable."
  type        = string
  sensitive   = true
  default     = "root"
}

variable "idrac_password" {
  description = "iDRAC password. Can also be set via TF_VAR_idrac_password environment variable."
  type        = string
  sensitive   = true
  default     = "calvin"
}

variable "idrac_ssl_insecure" {
  description = "Skip SSL certificate verification for iDRAC (use for self-signed certificates)"
  type        = bool
  default     = true
}
