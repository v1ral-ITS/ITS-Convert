# Demo PowerShell script

$name = "World"
$count = 42
Write-Host "Hello, $name"

$username = Read-Host "What is your name?"

if ($count -gt 50) {
    Write-Host "Many messages"
} elseif ($count -gt 10) {
    Write-Host "Some messages"
} else {
    Write-Host "Few messages"
}

for ($i = 0; $i -lt 5; $i++) {
    Write-Host "Item $i"
}

$x = 0
while ($x -lt 3) {
    Write-Host "x = $x"
    $x += 1
}

function Greet {
    param([string]$Name = "World")
    Write-Host "Hello, $Name!"
}

Greet -Name "Alice"

exit 0
