package app.input;

import com.error.ShowAlert;

import javafx.geometry.Point3D;
import javafx.scene.control.Alert.AlertType;

public class CellParameter {
	private Double ax,
	ay,
	az,
	bx,
	by,
	bz,
	cx,
	cy,
	cz;
	private int cellCount;
	public CellParameter() {
		ax=null;
		ay=null;
		az=null;
		bx=null;
		by=null;
		bz=null;
		cx=null;
		cy=null;
		cz=null;
		cellCount = 0;
	}
	public Double getAx() {return ax;}
	public Double getAy() {return ay;}
	public Double getAz() {return az;}
	public Double getBx() {return bx;}
	public Double getBy() {return by;}
	public Double getBz() {return bz;}
	public Double getCx() {return cx;}
	public Double getCy() {return cy;}
	public Double getCz() {return cz;}
	
	public void addCoor(double x, double y, double z) {
		if(cellCount==0) {ax=x;ay=y;az=z;}
		else if(cellCount==1) {bx=x;by=y;bz=z;}
		else if(cellCount==2) {cx=x;cy=y;cz=z;}
		else {
			ShowAlert.showAlert(AlertType.INFORMATION, "Warning", ">3 cellparameters detected in CellParameter.");
			//return;
		}
		//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", Integer.toString(cellCount)+
		//		Double.toString(x)+","+Double.toString(y)+","+Double.toString(z));
		cellCount++;
	}
	public String toString() {
		String strTmp="";
		strTmp+=(Double.toString(ax)+" "+Double.toString(ay)+" "+Double.toString(az)+"\n");
		strTmp+=(Double.toString(bx)+" "+Double.toString(by)+" "+Double.toString(bz)+"\n");
		strTmp+=(Double.toString(cx)+" "+Double.toString(cy)+" "+Double.toString(cz));
		return strTmp;
	}
	public Point3D crystalToCoordinate(double x, double y, double z) {
		Point3D avec = new Point3D(ax,ay,az);
		Point3D bvec = new Point3D(bx,by,bz);
		Point3D cvec = new Point3D(cx,cy,cz);
		return avec.multiply(x).add(bvec.multiply(y)).add(cvec.multiply(z));
	}
}
