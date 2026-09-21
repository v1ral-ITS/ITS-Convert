# import os
# import sys
$name = "World"
$count = 42
$pi = 3.14
$active = $true
Write-Host "Hello,", $name
Write-Host ""You have "$count" messages""
$username = Read-Host "What is your name? "
if ($count -gt 50) {
    Write-Host "Many messages"
} elseif ($count -gt 10) {
    Write-Host "Some messages"
else {
    Write-Host "Few messages"
}
for ($i = 0; $i -lt 5; $i += 1) {
    Write-Host ""Item "$i"
}
for ($i = 0; $i -lt 20; $i += 5) {
    Write-Host ""Step "$i"
}
$fruits = @("apple", "banana", "cherry")
foreach ($fruit in $fruits) {
    Write-Host $fruit
}
$x = 0
while ($x -lt 3) {
    Write-Host ""x = "$x"
    $x += 1
}
function greet {
    param(
        [string]$name,
        [string]$greeting = "Hello"
    )
    $message = "$greeting", "$name"!""
    Write-Host $message
    return $message
}
$result = "greet" @("Alice")
try {
    $value = "int" @("not a number")
} catch [e] {
    Write-Host ""Error: "$e"
} finally {
    Write-Host "Done"
}
$home = $env:HOME
Write-Host ""Home: "$home"
exit 0
