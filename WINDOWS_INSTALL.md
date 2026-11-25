# RelayNest Windows installation and signing

## Known Windows executable block

On the development laptop, the error “Windows cannot access the specified device, path, or file” was traced to a Windows Defender block for `dist\RelayNest.exe`. Other machines may have different causes for this message. Event 1121 reports the organization-managed ASR rule `01443614-CD74-433A-B99E-2ECDC07BFC25`. This rule checks executable reputation, including prevalence, age, and trusted-list criteria; the event alone does not say that RelayNest is malware.

The executable has been built, but the packaged app has not passed its tests because the development laptop blocked it. The Python desktop app's real send and receive workflows have passed tests. Do not distribute the executable as a verified release yet.

The source-based app opened with the WebView2 runtime on the development laptop. A Fixed Version `.cab` requires app-specific configuration and does not resolve an executable security block. If the runtime is missing on a target laptop, see https://developer.microsoft.com/microsoft-edge/webview2/ for the Evergreen Runtime.

## Run the development app

1. Open PowerShell in the RelayNest project directory.
2. Run:

   ```powershell
   npm start
   ```

3. The desktop window should open using the project Python environment. This is the development app, not the packaged `.exe`. If Python dependencies are missing, run `python -m pip install -r requirements-desktop.txt` using the same Python installation, or follow `DEVELOPMENT.md`.

## Resolve the executable block

The rule is managed by the device's administrator. Installing WebView2 or reinstalling dependencies will not change it. For the confirmed development-laptop block:

1. Give the device policy owner these details for review:

   ```text
   File: <your RelayNest project folder>\dist\RelayNest.exe
   Windows Defender Operational event: 1121
   ASR rule: 01443614-CD74-433A-B99E-2ECDC07BFC25
   ```

2. Alternatively, request a Microsoft review at https://www.microsoft.com/en-us/wdsi/filesubmission using the Attack Surface Reduction option. The block may prevent access to the file for submission. Microsoft review or signing does not guarantee an organization policy will allow it.
3. Once the responsible policy permits the file to run, open a new PowerShell window in the project folder and run:

   ```powershell
   npm run test:package
   npm run test:packaged-ui
   ```

4. Both tests must pass. Then double-click `dist\RelayNest.exe` and verify the window opens. A second-machine transfer test is still required before sharing it as a verified release.

Do not disable security controls or assume a different download source grants approval. On a Windows laptop you personally control, you can build and test from a GitHub checkout using the build steps below, subject to that laptop's own security settings.

## How to sign a Windows release

Signing gives a release a verifiable publisher identity and protects its contents against undetected changes. It is not required to run the development app, and it is not a guaranteed fix for this ASR block. Microsoft's guidance says that even signed new executables can receive reputation warnings: https://learn.microsoft.com/windows/apps/package-and-deploy/smartscreen-reputation . Do not purchase a certificate on the assumption that it will fix this particular managed policy.

1. Obtain access to a **trusted code-signing certificate and its private key** from your organization or a trusted certificate provider. A normal website TLS certificate is not sufficient. Providers may require identity checks and use a hardware token or cloud signing service. Follow the provider's installation instructions. Never share the private key or commit it to GitHub. Microsoft explains the available approaches at https://learn.microsoft.com/windows/apps/package-and-deploy/code-signing-options .
2. This project's `npm run sign` command supports a certificate available in the **current user's Windows certificate store** and accessible to Windows SignTool. Cloud-only services may need the provider's own signing instructions instead. In PowerShell, check the available certificates:

   ```powershell
   Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Select-Object Subject, Thumbprint, NotAfter, HasPrivateKey
   ```

   If the list is empty, install or connect the certificate according to its provider. If the private key is not available to SignTool, the command cannot sign. A self-signed certificate is not equivalent to a publicly trusted publisher certificate on another laptop.
3. Build the release first:

   ```powershell
   npm run build
   ```

   Stop if the build fails. Signing must be repeated after every rebuild because a rebuild changes the executable.
4. Find the certificate's **40-character thumbprint** from step 2 and the **HTTPS RFC 3161 timestamp URL** supplied by the certificate provider. Do not type the example URL as if it were a real signing service. Locate the x64 `signtool.exe` in your Windows SDK installation. Replace the SignTool path below if your SDK version differs. Enter the certificate thumbprint and provider URL when prompted:

   ```powershell
   $certThumbprint = Read-Host 'Paste the code-signing certificate thumbprint'
   $timestampUrl = Read-Host 'Paste the provider HTTPS timestamp URL'
   npm run sign -- -CertificateThumbprint $certThumbprint -TimestampUrl $timestampUrl -SignToolPath 'C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe'
   ```

   The script signs with SHA-256, requests a timestamp, and runs signature verification. It has not been tested with an actual certificate in this environment. If Defender blocks access to `RelayNest.exe`, signing may also fail until the policy owner or Microsoft resolves the block.
5. If signing and verification succeed, rerun `npm run test:package` and `npm run test:packaged-ui`. A valid signature proves neither that these tests pass nor that a managed device's rule will allow the executable.

## Build and test the Windows executable

On 64-bit Windows, install Python 3.13 and Node.js. In the project folder:

```powershell
npm run build
npm run test:engine
npm run test:package
npm run test:packaged-ui
```

The build creates `.venv` if needed and installs `requirements-build.txt`, so access to the configured Python package index is required. It writes `dist\RelayNest.exe`. If the build fails, do not use a pre-existing file in `dist` as if it were the new build.

`test:engine` tests the source transfer engine. `test:package` starts the actual packaged executable in self-test mode and checks a local sender, receiver, repeat skip and newer-source update. `test:packaged-ui` launches the actual executable's window, using WebView2 debugging only during the test, and tests sending and receiving with temporary files. The two packaged checks were blocked on the development laptop. They require Windows to permit the executable; the UI test additionally requires WebView2 and npm test dependencies.

The GitHub workflow `.github/workflows/windows-package.yml` builds and runs these packaged checks on a Windows runner before uploading its artifact. It has not yet been run in this repository. The runner needs working WebView2 desktop automation; a second-machine transfer test remains necessary. A GitHub artifact is not approval to run the file on a managed device.

## After the package passes: test on another laptop

1. Copy the verified `dist\RelayNest.exe` to the other Windows laptop. The packaged app is intended not to require Python or Node on that laptop. Confirm that laptop can run it and has WebView2 Runtime; request review if its policy blocks it.
2. Start RelayNest on both laptops. On the sender, choose **Send**, select a test folder and start sharing. Run `ipconfig` on the sender and note its local IPv4 address.
3. On the receiver, choose **Receive**. Enter the sender's address, for example `http://192.168.1.10:8000/`, using the actual IP and chosen port. Choose a separate destination folder and start the transfer. Check the file contents.
4. Receive again and check that unchanged files are skipped. Edit a source file, ensuring its modification time is at least two seconds later, and receive again to check that it updates. Stop sharing when finished. A firewall may require an approved rule for the selected port.

Use only a trusted network: the current sharing server is unauthenticated and unencrypted. Local files with equal or newer timestamps are skipped, timestamps have one-second precision, file contents are not hash-verified, and extra destination files are not deleted.
