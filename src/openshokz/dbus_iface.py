"""Shared D-Bus interface constants for the openshokz headset service."""

BUS_NAME = "com.github.jfenal.openshokz"
OBJECT_PATH = "/com/github/jfenal/openshokz/Headset"
INTERFACE_NAME = "com.github.jfenal.openshokz.Headset"

INTERFACE_XML = """
<node>
  <interface name="com.github.jfenal.openshokz.Headset">
    <method name="GetInfo">
      <arg type="a{sv}" name="info" direction="out"/>
    </method>
    <method name="ApplyEqPreset">
      <arg type="s" name="preset_arg" direction="in"/>
      <arg type="b" name="ok" direction="out"/>
    </method>
    <method name="ApplyLanguage">
      <arg type="s" name="lang_code" direction="in"/>
      <arg type="b" name="ok" direction="out"/>
    </method>
    <property name="Connected" type="b" access="read"/>
  </interface>
</node>
"""
