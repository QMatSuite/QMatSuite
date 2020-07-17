package com.env;

public class SystemInfo {
	private static String osName = null;
	public static String getOSName() {
		if(osName==null) {
			osName = System.getProperty ("os.name").toLowerCase();
		}
		return osName;
	}
	public static boolean isWindows() {
		return getOSName().contains("win");
	}
	public static boolean isUnix() {
		return (getOSName().contains("nix") || getOSName().contains("nux") || getOSName().contains("aix"));
	}
	public static boolean isMac() {
		return getOSName().contains("mac");
	}
}
