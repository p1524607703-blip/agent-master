$ErrorActionPreference = 'Stop'
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
if ($request.name -notmatch '^CodexRelay-[a-f0-9]{32}$') { throw 'Invalid key name' }
$provider = New-Object System.Security.Cryptography.CngProvider('Microsoft Platform Crypto Provider')
if ([System.Security.Cryptography.CngKey]::Exists($request.name, $provider)) {
    $key = [System.Security.Cryptography.CngKey]::Open($request.name, $provider)
} elseif ($request.action -eq 'create') {
    $parameters = New-Object System.Security.Cryptography.CngKeyCreationParameters
    $parameters.Provider = $provider
    $parameters.ExportPolicy = [System.Security.Cryptography.CngExportPolicies]::None
    $parameters.KeyUsage = [System.Security.Cryptography.CngKeyUsages]::Signing
    $key = [System.Security.Cryptography.CngKey]::Create([System.Security.Cryptography.CngAlgorithm]::ECDsaP256, $request.name, $parameters)
} else { throw 'Hardware key is missing; enroll this device again' }
try {
    if ($key.Provider.Provider -ne 'Microsoft Platform Crypto Provider' -or $key.ExportPolicy -ne [System.Security.Cryptography.CngExportPolicies]::None) { throw 'Hardware-only non-exportable key required' }
    $blob = $key.Export([System.Security.Cryptography.CngKeyBlobFormat]::EccPublicBlob)
    if ($blob.Length -ne 72 -or [BitConverter]::ToUInt32($blob, 4) -ne 32) { throw 'Expected P-256 key' }
    $point = New-Object byte[] 65
    $point[0] = 4
    [Array]::Copy($blob, 8, $point, 1, 64)
    $result = @{publicKey=[Convert]::ToBase64String($point); provider='windows-tpm-p256'}
    if ($request.action -eq 'sign') {
        $ecdsa = New-Object System.Security.Cryptography.ECDsaCng($key)
        try { $result.signature = [Convert]::ToBase64String($ecdsa.SignData([Convert]::FromBase64String($request.message), [System.Security.Cryptography.HashAlgorithmName]::SHA256)) }
        finally { $ecdsa.Dispose() }
    }
    $result | ConvertTo-Json -Compress
} finally { $key.Dispose() }
