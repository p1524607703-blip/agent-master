import Foundation
import CryptoKit

// The saved representation is enclave-wrapped and unusable on a different Mac.
// No software-key fallback. Prompts / enrollment errors propagate to the installer.
struct Input: Decodable { let action: String; let name: String; let message: String?; let handle: String? }
let input = try JSONDecoder().decode(Input.self, from: FileHandle.standardInput.readDataToEndOfFile())
var key: SecureEnclave.P256.Signing.PrivateKey
if let handle = input.handle, let data = Data(base64Encoded: handle) {
    key = try SecureEnclave.P256.Signing.PrivateKey(dataRepresentation: data)
} else if input.action == "create" {
    guard SecureEnclave.isAvailable else { fatalError("Secure Enclave is unavailable") }
    key = try SecureEnclave.P256.Signing.PrivateKey()
} else { fatalError("Missing hardware key") }
var output = ["publicKey": key.publicKey.x963Representation.base64EncodedString(), "provider": "macos-secure-enclave-p256"]
if input.action == "create" { output["handle"] = key.dataRepresentation.base64EncodedString() }
if input.action == "sign" {
    guard let message = input.message, let data = Data(base64Encoded: message) else { fatalError("Missing message") }
    output["signature"] = try key.signature(for: data).rawRepresentation.base64EncodedString()
}
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: output))
