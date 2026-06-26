use std::sync::Arc;
use std::time::Duration;

use reqwest::dns::{Addrs, Name, Resolve, Resolving};
use reqwest::Client;

/// Resolves hostnames to IPv4 addresses only.
///
/// Some networks (VPN, broken IPv6 routes) connect over IPv6 but fail TLS handshake.
/// Forcing IPv4 avoids `SSL_ERROR_SYSCALL` / DNS errors seen with Polymarket's API.
struct Ipv4Resolver;

impl Resolve for Ipv4Resolver {
    fn resolve(&self, name: Name) -> Resolving {
        let host = name.as_str().to_owned();

        Box::pin(async move {
            let mut addrs = Vec::new();

            for addr in tokio::net::lookup_host((host.as_str(), 0)).await? {
                if addr.is_ipv4() {
                    addrs.push(addr);
                }
            }

            if addrs.is_empty() {
                return Err(format!("no IPv4 address found for {host}").into());
            }

            Ok(Box::new(addrs.into_iter()) as Addrs)
        })
    }
}

pub fn build_client() -> Result<Client, reqwest::Error> {
    Client::builder()
        .dns_resolver(Arc::new(Ipv4Resolver))
        .connect_timeout(Duration::from_secs(15))
        .timeout(Duration::from_secs(60))
        .build()
}

pub async fn get_with_retry(client: &Client, url: &str, attempts: u32) -> Result<String, reqwest::Error> {
    let mut last_error = None;

    for attempt in 1..=attempts {
        match client.get(url).send().await {
            Ok(response) => return response.error_for_status()?.text().await,
            Err(error) => {
                eprintln!("Request attempt {attempt}/{attempts} failed: {error}");
                last_error = Some(error);

                if attempt < attempts {
                    tokio::time::sleep(Duration::from_secs(attempt as u64)).await;
                }
            }
        }
    }

    Err(last_error.expect("attempts must be at least 1"))
}
