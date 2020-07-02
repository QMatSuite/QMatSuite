package app.input;

import com.error.ShowAlert;

import javafx.scene.control.Alert.AlertType;

public class Cell {
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
	public Cell() {
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
	public void addCoor(double x, double y, double z) {
		if(cellCount==0) {ax=x;ay=y;az=z;}
		else if(cellCount==1) {bx=x;by=y;bz=z;}
		else if(cellCount==2) {cx=x;cy=y;cz=z;}
		else {
			ShowAlert.showAlert(AlertType.INFORMATION, "Warning", ">3 cellparameters detected.");
			return;
		}
		cellCount++;
	}
	public String toString() {
		String strTmp="";
		strTmp+=(Double.toString(ax)+" "+Double.toString(ay)+" "+Double.toString(az)+"\n");
		strTmp+=(Double.toString(bx)+" "+Double.toString(by)+" "+Double.toString(bz)+"\n");
		strTmp+=(Double.toString(cx)+" "+Double.toString(cy)+" "+Double.toString(cz));
		return strTmp;
	}
}
