package android.os;
import java.util.HashMap;
import java.util.Map;
public final class SystemProperties {
    public static final Map<String, String> VALUES = new HashMap<String, String>();
    public static String get(String key) { String value = VALUES.get(key); return value == null ? "" : value; }
}
