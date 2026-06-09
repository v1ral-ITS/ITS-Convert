package main

import (
    "bufio"
    "fmt"
    "os"
)

func main() {
    // import "os"
    // import "sys"
    name := 'World'
    count := 42
    pi := 3.14
    active := true
    fmt.Printf("%v %v\n", 'Hello,', name)
    fmt.Println('You have {count} messages')
    scanner := bufio.NewScanner(os.Stdin)
    fmt.Print("What is your name? ")
    scanner.Scan()
    username := scanner.Text()
    if count > 50 {
        fmt.Println('Many messages')
    } else if count > 10 {
        fmt.Println('Some messages')
    } else {
        fmt.Println('Few messages')
    }
    for i := 0; i < 5; i++ {
        fmt.Println('Item {i}')
    }
    for i := 0; i < 20; i++ {
        fmt.Println('Step {i}')
    }
    fruits := []any{'apple', 'banana', 'cherry'}
    for _, fruit := range fruits {
        fmt.Println(fruit)
    }
    x := 0
    for x < 3 {
        fmt.Println('x = {x}')
        x += 1
    }
    func greet(name any, greeting any) any {
        message := '{greeting}, {name}!'
        fmt.Println(message)
        return message
    }
    result := None
    // Go: no try-catch; using defer/recover
    value := None
    home := os.Getenv("HOME")
    fmt.Println('Home: {home}')
    os.Exit(0)
}
