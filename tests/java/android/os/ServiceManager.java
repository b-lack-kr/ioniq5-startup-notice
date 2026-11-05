package android.os;
public final class ServiceManager {
    public static int lookups;
    public static String bootCompletedOnLookup;
    public static IBinder binder = new IBinder() {};
    public static IBinder getService(String name) {
        lookups++;
        if (!"com.hkmc.factory".equals(name)) throw new AssertionError(name);
        if (bootCompletedOnLookup != null) {
            SystemProperties.VALUES.put("sys.boot_completed", bootCompletedOnLookup);
        }
        return binder;
    }
}
