# Feature Specification: Universal Multi-Platform Deployment System

**Feature Branch**: `001-universal-deployment`
**Created**: 2025-12-30
**Status**: Draft
**Input**: User description: "Universal deployment system for Claude Code Proxy that makes installation one-click easy on any platform (macOS, Linux, Windows, Docker, cloud services). Use existing libraries and package managers to minimize custom code while maximizing platform coverage. Include: Docker one-liner installer, Homebrew formula, cloud deploy buttons (Railway/Render/Fly.io), Chocolatey package, Snap package, Helm chart for Kubernetes, and standalone binaries. Prioritize developer experience and leverage existing packaging ecosystems."

## Clarifications

### Session 2025-12-30

- Q: How should the installer endpoint at https://joachimbrindeau.github.io/ccproxy-api/install.sh be hosted and managed? → A: GitHub Pages with custom domain (joachimbrindeau.github.io/ccproxy-api/install.sh CNAME to joachimbrindeau.github.io/claude-code-proxy/install.sh) - zero cost, automatic deployment via GitHub Actions
- Q: What format should OAuth credentials use for export/import between installation methods? → A: Web UI buttons on /accounts/ page for export (browser download API) and import (browser file upload API) of accounts.json file - uses standard browser APIs to minimize custom code

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Docker Developer Quick Start (Priority: P1)

A developer wants to try Claude Code Proxy immediately without installing anything except Docker. They run a single command that downloads, configures, and starts Claude Code Proxy, then automatically opens their browser to the OAuth setup page.

**Why this priority**: Docker is cross-platform and already widely installed among developers. This covers 60%+ of target users with minimal maintenance burden. Delivers immediate value with existing infrastructure (compose.dist.yaml already exists).

**Independent Test**: Can be fully tested by running the installer command on a machine with Docker installed and verifying the service starts and browser opens to http://localhost:8000/accounts/. Delivers complete working proxy without any other dependencies.

**Acceptance Scenarios**:

1. **Given** a developer has Docker installed, **When** they run `curl -fsSL https://joachimbrindeau.github.io/ccproxy-api/install.sh | sh`, **Then** the installer detects Docker, downloads the compose file, starts the service, and opens their browser to the accounts page
2. **Given** a developer does NOT have Docker installed on macOS, **When** they run the installer, **Then** the system offers to install Docker via Homebrew automatically
3. **Given** a developer does NOT have Docker installed on Linux, **When** they run the installer, **Then** the system provides clear instructions for installing Docker on their distribution
4. **Given** Claude Code Proxy is already running via Docker, **When** they run the installer again, **Then** the system detects the existing installation and offers to upgrade or restart
5. **Given** the service starts successfully, **When** the browser opens, **Then** the developer sees the account management UI and can immediately begin OAuth setup

---

### User Story 2 - macOS/Linux Developer Native Installation (Priority: P1)

A macOS or Linux developer wants Claude Code Proxy integrated with their system using their native package manager (Homebrew). They install with a single command, and the service runs as a background process that starts automatically on boot.

**Why this priority**: Native package managers provide the best developer experience on macOS/Linux. This is P1 alongside Docker because it serves a distinct audience (developers who prefer native installs over containers). Homebrew has 25%+ of macOS developers.

**Independent Test**: Can be tested by running `brew install joachimbrindeau/tap/claude-code-proxy && brew services start claude-code-proxy` on macOS or Linux, verifying the service starts as a background daemon, and confirming the web UI is accessible.

**Acceptance Scenarios**:

1. **Given** a developer on macOS, **When** they run `brew install joachimbrindeau/tap/claude-code-proxy`, **Then** Homebrew downloads and installs Claude Code Proxy with all dependencies in under 60 seconds
2. **Given** Claude Code Proxy is installed via Homebrew, **When** they run `brew services start claude-code-proxy`, **Then** the service starts as a launchd daemon and automatically opens their browser to the setup page
3. **Given** the claude-code-proxy service is running, **When** the system reboots, **Then** the service automatically restarts via brew services
4. **Given** a new version is released, **When** they run `brew upgrade claude-code-proxy`, **Then** the service updates without losing OAuth credentials or configuration
5. **Given** Claude Code Proxy is running as a brew service, **When** they run `brew services info claude-code-proxy`, **Then** they see the service status, logs location, and port information

---

### User Story 3 - Cloud Platform One-Click Deploy (Priority: P2)

A user wants to host Claude Code Proxy in the cloud without managing infrastructure. They click a "Deploy to Railway" button from the README, the service deploys automatically with all dependencies, and they receive a public URL to access the OAuth setup interface.

**Why this priority**: Cloud deploy buttons remove all local installation friction but require the user to have/create a cloud account and accept potential costs. This is P2 because it serves users who specifically want cloud hosting rather than local installation. Provides instant value for teams sharing access.

**Independent Test**: Can be tested by clicking the deploy button, verifying Railway/Render/Fly.io provisions the service with persistent storage for OAuth credentials, and accessing the service via the generated public URL.

**Acceptance Scenarios**:

1. **Given** a user clicks "Deploy to Railway" in the README, **When** Railway provisions the service, **Then** the deployment includes a persistent volume for `/data/accounts.json` to preserve OAuth tokens
2. **Given** the service deploys on Railway, **When** deployment completes, **Then** Railway provides a public HTTPS URL (e.g., `https://claude-code-proxy-xyz.up.railway.app`) that's immediately accessible
3. **Given** the service is accessible via public URL, **When** users visit `/accounts/`, **Then** OAuth callbacks work correctly with the public URL
4. **Given** a deployment exists, **When** a new git commit is pushed, **Then** the cloud platform automatically redeploys without losing OAuth credentials
5. **Given** deployments on Render and Fly.io, **When** users click their respective deploy buttons, **Then** each platform correctly configures environment variables for OAuth redirect URIs

---

### User Story 4 - Windows Developer Package Installation (Priority: P2)

A Windows developer wants to install Claude Code Proxy using their preferred Windows package manager (Chocolatey). They run a single choco command, and Claude Code Proxy installs with auto-start capabilities and appears in Windows Services.

**Why this priority**: Windows developers represent 10-15% of the target audience. Chocolatey provides a standard installation method Windows developers expect. This is P2 because Docker works on Windows too, so it's an alternative to the P1 Docker installer rather than the only option.

**Independent Test**: Can be tested by running `choco install claude-code-proxy` on Windows, verifying it installs to Program Files, creates a Windows Service, and is accessible at localhost:8000.

**Acceptance Scenarios**:

1. **Given** a Windows developer, **When** they run `choco install claude-code-proxy`, **Then** Chocolatey installs Claude Code Proxy and all Python dependencies in under 2 minutes
2. **Given** installation completes, **When** the installer finishes, **Then** Claude Code Proxy is registered as a Windows Service set to auto-start
3. **Given** Claude Code Proxy is installed, **When** they run `claude-code-proxy serve` or start the Windows Service, **Then** the web interface becomes available at http://localhost:8000
4. **Given** Claude Code Proxy is running as a Windows Service, **When** they run `choco upgrade claude-code-proxy`, **Then** the service stops, updates, and restarts automatically while preserving OAuth credentials in %APPDATA%/claude-code-proxy/

---

### User Story 5 - Linux Desktop User Snap Installation (Priority: P3)

A Linux desktop user (Ubuntu, Fedora, etc.) wants to install Claude Code Proxy from their distribution's app store or package manager. They use Snap to install with automatic updates and sandboxed security.

**Why this priority**: Snap reaches Linux desktop users across many distributions, but represents a smaller audience (~5% of target users). This is P3 because these users can also use Docker (P1), making this an alternative for those who prefer native packages.

**Independent Test**: Can be tested by running `snap install claude-code-proxy`, verifying it creates a background daemon, and confirming the web UI is accessible with proper permissions for OAuth credential storage.

**Acceptance Scenarios**:

1. **Given** a Linux user, **When** they run `snap install claude-code-proxy`, **Then** Snap installs Claude Code Proxy in a sandboxed environment with network and home directory access permissions
2. **Given** Claude Code Proxy is installed via Snap, **When** they run `snap start claude-code-proxy`, **Then** the service starts as a systemd daemon and is accessible at http://localhost:8000
3. **Given** Snap manages Claude Code Proxy, **When** updates are available, **Then** Snap automatically updates in the background and restarts the service
4. **Given** Claude Code Proxy stores OAuth credentials, **When** running in the Snap sandbox, **Then** credentials persist in the Snap-specific home directory across updates

---

### User Story 6 - DevOps Engineer Kubernetes Deployment (Priority: P3)

A DevOps engineer wants to deploy Claude Code Proxy to a Kubernetes cluster for production use with multiple replicas. They use a Helm chart that handles all Kubernetes resources, persistent storage for OAuth credentials, and ingress configuration for HTTPS access.

**Why this priority**: Kubernetes deployments serve enterprise and high-availability scenarios but represent a smaller specialized audience (~8% of target users). This is P3 because it's not needed for initial adoption but becomes important for production/enterprise use cases.

**Independent Test**: Can be tested by running `helm install claude-code-proxy claude-code-proxy/claude-code-proxy` on a test Kubernetes cluster and verifying the deployment creates pods, services, persistent volume claims, and optionally ingress resources.

**Acceptance Scenarios**:

1. **Given** a DevOps engineer with kubectl access, **When** they run `helm repo add claude-code-proxy https://joachimbrindeau.github.io/claude-code-proxy-helm && helm install claude-code-proxy claude-code-proxy/claude-code-proxy`, **Then** Helm deploys Claude Code Proxy with ConfigMaps for environment variables, PersistentVolumeClaim for `/config`, and a LoadBalancer service
2. **Given** Claude Code Proxy is deployed in Kubernetes, **When** they configure values.yaml with custom settings, **Then** the Helm chart applies all configurations (replicas, resources, ingress, TLS) correctly
3. **Given** multiple Claude Code Proxy pods exist, **When** OAuth credentials are stored, **Then** all pods share the same PersistentVolume to maintain consistent authentication state
4. **Given** a Helm deployment exists, **When** they run `helm upgrade claude-code-proxy claude-code-proxy/claude-code-proxy --set image.tag=v2.0`, **Then** Kubernetes performs a rolling update without OAuth credential loss
5. **Given** Ingress is enabled in values.yaml, **When** deployment completes, **Then** Claude Code Proxy is accessible via the configured hostname with TLS termination

---

### User Story 7 - Pre-built Binary for Any Platform (Priority: P4)

A user without Docker, package managers, or cloud access wants to download a single executable file and run Claude Code Proxy. They download the appropriate binary for their platform (macOS-arm64, macOS-x64, linux-amd64, windows-amd64), run it, and the browser auto-opens to the setup page.

**Why this priority**: Standalone binaries provide maximum portability but serve edge cases (~2% of users). This is P4 because all higher-priority methods provide better experiences (auto-updates, system integration). Binaries are a fallback for constrained environments.

**Independent Test**: Can be tested by downloading the platform-specific binary, running it without any installation, and verifying Claude Code Proxy starts and opens the browser automatically.

**Acceptance Scenarios**:

1. **Given** a user downloads claude-code-proxy-darwin-arm64, **When** they run `chmod +x claude-code-proxy-darwin-arm64 && ./claude-code-proxy-darwin-arm64`, **Then** the binary starts the FastAPI server and opens Safari to http://localhost:8000/accounts/
2. **Given** a Windows user downloads claude-code-proxy-windows-amd64.exe, **When** they double-click the executable, **Then** Windows may show an unsigned binary warning, but after approval, Claude Code Proxy starts and opens the default browser
3. **Given** Claude Code Proxy runs from a binary, **When** users need to store OAuth credentials, **Then** credentials save to OS-appropriate directories (macOS: ~/Library/Application Support/claude-code-proxy/, Linux: ~/.config/claude-code-proxy/, Windows: %APPDATA%/claude-code-proxy/)
4. **Given** binaries are built for releases, **When** GitHub Actions runs, **Then** binaries are created for all 4 platforms (darwin-arm64, darwin-amd64, linux-amd64, windows-amd64) and attached to GitHub releases

---

### Edge Cases

- **What happens when Docker is not installed and automatic installation fails?** The installer script provides clear manual installation instructions specific to the user's operating system and offers to retry after manual installation
- **What happens when port 8000 is already in use?** The installer detects the port conflict and either offers to stop the existing service or prompts for a different port via environment variable configuration
- **What happens when OAuth callbacks fail due to network restrictions or firewall rules?** The web UI displays clear error messages with troubleshooting steps for common network issues and offers an alternative manual token configuration method
- **What happens when persistent storage (Docker volume, PVC) fails to mount?** The service starts in a degraded state, displays a warning that OAuth credentials won't persist, and provides instructions for fixing storage permissions
- **What happens when upgrading from one installation method to another (e.g., Docker to Homebrew)?** Users visit the /accounts/ page, click "Export Accounts" to download their accounts.json file, install Claude Code Proxy via the new method, then click "Import Accounts" to upload the file and restore their OAuth credentials
- **What happens when package manager repositories have approval delays or are rejected?** Documentation provides alternative installation methods and the project maintains direct downloads as fallbacks until approval completes
- **What happens when users install on unsupported platforms (BSD, ARM Linux, old macOS)?** The installer detects unsupported platforms and recommends the closest supported alternative or Docker as a universal fallback

## Requirements *(mandatory)*

### Functional Requirements

#### Installation & Distribution
- **FR-001**: System MUST provide a Docker-based installer script at `scripts/install.sh` that detects Docker installation, downloads compose.dist.yaml, starts the service, and opens the browser to the accounts page
- **FR-002**: System MUST provide a publicly accessible installer endpoint at `https://joachimbrindeau.github.io/ccproxy-api/install.sh` that serves the Docker installer script via curl. The endpoint MUST be hosted on GitHub Pages with a custom domain CNAME pointing to joachimbrindeau.github.io/claude-code-proxy/install.sh, deployed automatically via GitHub Actions
- **FR-003**: System MUST provide a Homebrew formula in a dedicated tap repository (`joachimbrindeau/homebrew-tap`) that installs Claude Code Proxy with all dependencies using standard Homebrew practices
- **FR-004**: System MUST provide cloud deployment configurations for Railway (`railway.json`), Render (`render.yaml`), and Fly.io (`fly.toml`) that include persistent storage mounting for OAuth credentials
- **FR-005**: System MUST provide a Chocolatey package specification (`.nuspec`) that installs Claude Code Proxy on Windows with automatic Windows Service registration
- **FR-006**: System MUST provide a Snap package configuration (`snapcraft.yaml`) that sandboxes Claude Code Proxy while maintaining necessary permissions for network access and home directory storage
- **FR-007**: System MUST provide a Helm chart in a dedicated chart repository that deploys Claude Code Proxy to Kubernetes with ConfigMap, PersistentVolumeClaim, Service, and optional Ingress resources
- **FR-008**: System MUST provide pre-built standalone binaries for macOS (arm64 and x64), Linux (amd64), and Windows (amd64) attached to GitHub releases

#### Library & Package Manager Usage
- **FR-009**: Docker installer MUST use the existing `compose.dist.yaml` file without creating custom Docker configurations
- **FR-010**: Homebrew formula MUST use `homebrew-pypi-poet` or similar tools to auto-generate Python dependency specifications rather than manual dependency listing
- **FR-011**: Cloud deployment configurations MUST use each platform's native configuration format without custom deployment scripts
- **FR-012**: Chocolatey package MUST leverage Chocolatey's built-in Windows Service integration rather than custom service management code
- **FR-013**: Snap package MUST use Snapcraft's daemon primitives for service management rather than custom systemd unit files
- **FR-014**: Helm chart MUST use standard Kubernetes resource templates and Helm's built-in value templating rather than custom Kubernetes manifests
- **FR-015**: Standalone binaries MUST use PyInstaller's `--onefile` mode and standard library bundling without custom Python runtime embedding
- **FR-016**: All package managers (brew, choco, snap) MUST use their respective testing/linting tools (brew test, choco pack --test, snapcraft lint) to validate package quality

#### Automation & CI/CD
- **FR-017**: System MUST provide GitHub Actions workflows that automatically build and publish packages for all supported installation methods on new git tags
- **FR-018**: GitHub Actions MUST build standalone binaries for all 4 platforms (darwin-arm64, darwin-amd64, linux-amd64, windows-amd64) and attach them to GitHub releases
- **FR-019**: GitHub Actions MUST update Homebrew formula with new release versions and SHA256 checksums automatically using existing Homebrew tap automation
- **FR-020**: GitHub Actions MUST package and publish Helm charts to GitHub Pages-based chart repository using `helm package` and `helm repo index` commands
- **FR-021**: GitHub Actions MUST deploy the installer script to GitHub Pages automatically on commits to main branch, making it accessible at https://joachimbrindeau.github.io/ccproxy-api/install.sh via CNAME configuration

#### User Experience
- **FR-022**: Docker installer MUST automatically open the user's default browser to `http://localhost:8000/accounts/` upon successful service start
- **FR-023**: Homebrew installation MUST provide post-install instructions via `brew info claude-code-proxy` that include service start commands and web UI URL
- **FR-024**: All installation methods MUST preserve OAuth credentials across upgrades in platform-appropriate persistent storage locations
- **FR-025**: The /accounts/ page MUST provide "Export Accounts" button that downloads accounts.json using browser download API and "Import Accounts" button that uploads accounts.json using browser file upload API, enabling OAuth credential migration between installation methods without custom code
- **FR-026**: All installation methods MUST provide clear documentation for troubleshooting common issues (port conflicts, permission errors, network problems)
- **FR-027**: README MUST include visible "Deploy to" buttons for Railway, Render, and Fly.io that users can click to deploy immediately

#### Service Management
- **FR-028**: Homebrew installation MUST integrate with `brew services` for background daemon management (start, stop, restart)
- **FR-029**: Chocolatey installation MUST register Claude Code Proxy as a Windows Service with automatic startup configured
- **FR-030**: Snap installation MUST register Claude Code Proxy as a systemd daemon with automatic startup and restart policies
- **FR-031**: Docker installer MUST configure the service with `restart: unless-stopped` policy in the compose file
- **FR-032**: All service configurations MUST include health checks that validate the web UI is accessible on the configured port

### Key Entities

- **Installer Script**: A shell script (`scripts/install.sh`) that detects the environment, checks for Docker, downloads configurations, starts services, and opens the browser. Minimal custom logic - primarily orchestrates existing tools (curl, docker compose, platform-specific browser commands).

- **Package Specifications**: Configuration files for each package manager (Formula/claude-code-proxy.rb for Homebrew, claude-code-proxy.nuspec for Chocolatey, snapcraft.yaml for Snap) that declare dependencies, installation paths, service configurations, and metadata. All use declarative formats provided by the package manager ecosystem.

- **Cloud Deployment Configs**: Platform-specific configuration files (railway.json, render.yaml, fly.toml) that declare service settings, environment variables, persistent volume mounts, and health checks. Follow each platform's schema without custom deployment logic.

- **Helm Chart**: A collection of Kubernetes resource templates (deployment.yaml, service.yaml, configmap.yaml, pvc.yaml, ingress.yaml) with values.yaml for customization. Uses Helm's built-in templating and does not include custom operators or controllers.

- **Standalone Binary**: A self-contained executable produced by PyInstaller that bundles Python runtime, Claude Code Proxy code, and all dependencies. Includes minimal startup logic to set config paths and launch the FastAPI server.

- **GitHub Actions Workflows**: YAML workflow files (.github/workflows/) that automate building, testing, and publishing packages. Uses existing actions from GitHub Marketplace (actions/checkout, docker/build-push-action, helm/chart-releaser-action) rather than custom build scripts.

- **Installation Documentation**: README sections and dedicated docs files (docs/installation/) that provide platform-specific installation guides, troubleshooting steps, and OAuth setup walkthroughs. Written for non-technical users with screenshots and command examples.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user with Docker installed can go from zero to running Claude Code Proxy in under 90 seconds by copying a single command
- **SC-002**: A macOS developer can install Claude Code Proxy via Homebrew and have it running as a background service in under 2 minutes
- **SC-003**: A user can deploy Claude Code Proxy to Railway/Render/Fly.io by clicking a button and receive a working public URL in under 5 minutes
- **SC-004**: All installation methods successfully preserve OAuth credentials across version upgrades without user intervention
- **SC-005**: 95%+ of users successfully complete installation on their first attempt without needing to consult troubleshooting documentation
- **SC-006**: The project maintains 8 different installation methods (Docker, Homebrew, Railway, Render, Fly.io, Chocolatey, Snap, Binaries) with less than 5 hours/month maintenance effort due to automation
- **SC-007**: GitHub Actions automatically build and publish new releases across all platforms within 15 minutes of tagging a release
- **SC-008**: Installation documentation provides a working installation path for 95%+ of target users (developers on macOS, Linux, Windows, or cloud platforms)
- **SC-009**: Package manager submissions (Homebrew, Chocolatey, Snap) pass automated quality checks on first submission attempt
- **SC-010**: Docker installer script successfully detects and handles missing Docker on macOS, Linux, and Windows with appropriate guidance

## Assumptions

1. **Target Audience**: Primary users are developers and DevOps engineers comfortable with command-line interfaces. Non-technical users are not the primary target but may benefit from cloud deploy buttons.

2. **Docker Availability**: The Docker installation path assumes users either have Docker installed or can install it when prompted. Docker Desktop on Windows/macOS and docker.io on Linux are the standard installation paths.

3. **Package Manager Approval**: Homebrew tap repositories can be created without approval. Chocolatey and Snap require community approval which may take 1-2 weeks. Documentation will provide interim alternatives (Docker, direct downloads) during approval periods.

4. **OAuth Flow Compatibility**: All installation methods assume the existing OAuth PKCE flow works correctly and that localhost:54545 callback or configurable redirect URIs are sufficient for authentication.

5. **Persistent Storage**: Each platform provides reliable persistent storage (Docker volumes, Homebrew's Cellar, Windows %APPDATA%, Snap's home binding, Kubernetes PVCs, cloud provider volumes) that survives service restarts and upgrades.

6. **Build Infrastructure**: GitHub Actions free tier provides sufficient build minutes for multi-platform binary compilation. If limits are exceeded, project maintainers can upgrade to paid Actions or use external CI/CD.

7. **Code Signing**: Initial releases will provide unsigned binaries with clear warnings. Code signing (Apple Developer account $99/year, Windows cert $100-400/year) may be added in future based on user demand and security policies.

8. **Maintenance Capacity**: Project maintainers can dedicate ~5 hours/month to monitoring package manager repositories, responding to submission feedback, and updating automation workflows.

9. **Platform Support**: The project supports actively maintained platforms (macOS 12+, Windows 10+, Ubuntu LTS, Debian stable, recent Fedora). Legacy platforms (macOS 10.x, Windows 7, CentOS 6) are explicitly unsupported.

10. **Network Access**: Installation methods assume users have internet access to download packages, Docker images, and dependencies. Air-gapped or restricted network installations are out of scope for the initial release.

## Out of Scope

1. **Desktop GUI Applications**: Electron or Tauri-based desktop applications with graphical installers are not included. All installations are command-line or web-based.

2. **Mobile Applications**: iOS and Android apps for Claude Code Proxy management or usage are not included.

3. **Browser Extensions**: Chrome, Firefox, or Safari extensions for Claude Code Proxy integration are not included.

4. **Managed Hosted Service**: A fully managed SaaS offering where the project maintainers host and operate Claude Code Proxy for users is not included.

5. **Enterprise Marketplace Listings**: AWS Marketplace, Azure Marketplace, Google Cloud Marketplace listings are not included in initial release due to lengthy approval processes and compliance requirements.

6. **Terraform Modules**: Infrastructure-as-Code modules for AWS, GCP, Azure automated deployment are not included in initial release but may be added based on demand.

7. **Configuration Wizards**: Interactive CLI or GUI wizards for post-installation configuration are not included. Users configure via environment variables or editing compose.yaml/values.yaml.

8. **Automatic Cross-Platform Detection**: Tools that automatically detect and migrate OAuth credentials between installation methods without user action (e.g., automatically finding and importing credentials when switching from Docker to Homebrew) are not included. Users must manually export/import via the web UI buttons.

9. **Custom Linux Package Repositories**: Dedicated APT (Debian/Ubuntu) or YUM (RHEL/CentOS) repositories with signed packages are not included. Linux users can use Docker, Snap, or standalone binaries.

10. **Windows MSI Installers**: Traditional Windows Installer (.msi) packages with graphical install wizards are not included. Windows users can use Chocolatey, Docker, or standalone executables.

11. **Code Signing Infrastructure**: Automated code signing pipelines for macOS notarization and Windows Authenticode signing are not included in initial release. Binaries will be unsigned with appropriate warnings.

12. **Multi-Architecture Binaries**: Support for non-x64/ARM64 architectures (32-bit, RISC-V, PowerPC) is not included. Only darwin-arm64, darwin-amd64, linux-amd64, and windows-amd64 are supported.
