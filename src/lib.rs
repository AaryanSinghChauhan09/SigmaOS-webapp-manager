#[derive(Debug, Clone)]
pub struct WebAppDescriptor {
    pub name: String,
    pub launch_url: String,
    pub isolated_profile_dir: String,
}

#[derive(Debug, Default)]
pub struct WebAppManager {
    apps: Vec<WebAppDescriptor>,
}

impl WebAppManager {
    pub fn new() -> Self { Self::default() }
    pub fn create_webapp(&mut self, name: &str, url: &str) {
        self.apps.push(WebAppDescriptor {
            name: name.to_string(),
            launch_url: url.to_string(),
            isolated_profile_dir: format!("~/.local/share/webapps/{}", name),
        });
    }
    pub fn count(&self) -> usize { self.apps.len() }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_webapp_creation() {
        let mut mgr = WebAppManager::new();
        mgr.create_webapp("GitHub", "https://github.com");
        assert_eq!(mgr.count(), 1);
    }
}
