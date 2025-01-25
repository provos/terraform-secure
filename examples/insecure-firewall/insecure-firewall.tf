provider "google" {
  project = "fit-accumulator-440500-e5"
  region  = "us-east1`"
}

resource "google_compute_network" "default" {
  name                    = "default-network"
  auto_create_subnetworks = true
}

resource "google_compute_firewall" "allow-http-https" {
  name    = "allow-http-https"
  network = google_compute_network.default.self_link

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/8"]
  target_tags   = ["http-server"]
}

resource "google_compute_instance" "vm_instance" {
  name         = "example-vm"
  machine_type = "e2-micro"
  zone         = "us-east1-b"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    network = google_compute_network.default.name

    access_config {
      # Required to allow access from the internet
    }
  }

  metadata = {
    enable-oslogin = "FALSE"
  }

  tags = ["http-server"]
}

resource "google_compute_address" "external_ip" {
  name   = "vm-external-ip"
  region = "us-east1"
}

output "instance_external_ip" {
  value = google_compute_instance.vm_instance.network_interface[0].access_config[0].nat_ip
}
