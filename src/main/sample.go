package main

import (
	"sample"
	"fmt"
)

const (
	NSTitledWindowMask = 1 << 0
	NSBackingStoreBuffered = 2
)


func main() {
    app := sample.NSApplication_sharedApplication()
    //app.SetActivationPolicy(sample.NSApplicationActivationPolicyRegular)
	win := sample.NSWindow_initWithContentRectStyleMaskBackingDefer(sample.NSRect{0,0, 200,200}, NSTitledWindowMask, NSBackingStoreBuffered, false)
    win.CascadeTopLeftFromPoint(sample.NSPoint{20,20})
    win.SetTitle(sample.NSString_initWithUTF8String("SomeApp"))
    win.MakeKeyAndOrderFront(nil)
    app.ActivateIgnoringOtherApps(true)

	fmt.Println(app, win)
	fmt.Println(app.GetClassName(), win.GetClassName())

	app.Run();
}


