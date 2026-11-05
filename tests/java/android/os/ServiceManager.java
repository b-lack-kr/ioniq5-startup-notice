package android.os;
public final class ServiceManager {
    public static int lookups;
    public static IBinder binder = new IBinder() {};
    public static IBinder getService(String name) {
        lookups++;
        if (!"com.hkmc.factory".equals(name)) throw new AssertionError(name);
        return binder;
    }
}
