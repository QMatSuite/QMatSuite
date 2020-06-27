package app.input;

import java.io.Serializable;

public class Kpoint implements Serializable{
	/**
	 * 
	 */
	private static final long serialVersionUID = 5025931913909260630L;
	private String label;
	private double kx;
	private double ky;
	private double kz;
	private int nk;
	public Kpoint(String lb, double kx, double ky, double kz, int nk) {
		this.label = lb;
		this.kx = kx;this.ky = ky;this.kz = kz;this.nk = nk;
	}
	public String getLabel() {
		return label;
	}
	public void setLabel(String label) {
		this.label = label;
	}
	public double getKx() {
		return kx;
	}
	public void setKx(double kx) {
		this.kx = kx;
	}
	public double getKz() {
		return kz;
	}
	public void setKz(double kz) {
		this.kz = kz;
	}
	public double getKy() {
		return ky;
	}
	public void setKy(double ky) {
		this.ky = ky;
	}
	public int getNk() {
		return nk;
	}
	public void setNk(int nk) {
		this.nk = nk;
	}
}
