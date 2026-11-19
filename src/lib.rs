#![forbid(unsafe_code)]
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


impl WebAppManager {
    pub fn get_webapp(&self, name: &str) -> Option<&WebAppDescriptor> {
        self.apps.iter().find(|a| a.name == name)
    }
    pub fn remove_webapp(&mut self, name: &str) -> bool {
        if let Some(pos) = self.apps.iter().position(|a| a.name == name) {
            self.apps.remove(pos);
            true
        } else {
            false
        }
    }
    pub fn is_empty(&self) -> bool {
        self.apps.is_empty()
    }
}

#[cfg(test)]
mod webapp_manager_extra_tests {
    use super::*;

    #[test]
    fn test_get_webapp_aaa() {
        // Arrange
        let mut mgr = WebAppManager::new();
        mgr.create_webapp("Slack", "https://app.slack.com");
        // Act
        let app = mgr.get_webapp("Slack");
        // Assert
        assert!(app.is_some());
        assert_eq!(app.unwrap().launch_url, "https://app.slack.com");
        assert!(app.unwrap().isolated_profile_dir.contains("Slack"));
    }

    #[test]
    fn test_remove_webapp_aaa() {
        // Arrange
        let mut mgr = WebAppManager::new();
        mgr.create_webapp("Notion", "https://notion.so");
        assert_eq!(mgr.count(), 1);
        // Act
        let removed = mgr.remove_webapp("Notion");
        // Assert
        assert!(removed);
        assert_eq!(mgr.count(), 0);
        assert!(!mgr.remove_webapp("Notion"));
    }

    #[test]
    fn test_empty_manager_state_aaa() {
        // Arrange & Act
        let mgr = WebAppManager::new();
        // Assert
        assert!(mgr.is_empty());
        assert_eq!(mgr.count(), 0);
    }

    #[test]
    fn test_multiple_webapps_aaa() {
        // Arrange
        let mut mgr = WebAppManager::new();
        // Act
        mgr.create_webapp("App1", "https://app1.org");
        mgr.create_webapp("App2", "https://app2.org");
        // Assert
        assert_eq!(mgr.count(), 2);
    }
}
