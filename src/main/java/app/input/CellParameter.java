/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.input;

import core.com.error.ShowAlert;
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
	private boolean isNull() {
		return (ax==null || ay==null || az==null||
				bx==null || by==null || bz==null||
				cx==null || cy==null || cz==null);
	}
	public String toString() {
		String strTmp="";
		if(isNull()) {return "Null in CellParameters.";}
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
