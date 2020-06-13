/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.input.geo;


import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;
import com.consts.ChemicalElements;

public class Atom extends Chemical {
	/**
	 * 
	 */
	private static final long serialVersionUID = 2080346685186523233L;
	
	//coordinates "as is"
	private Coordinate xcoor;
	private Coordinate ycoor;
	private Coordinate zcoor;

	
	public Atom(ChemicalElements species, Double x, Double y, Double z, Boolean fix_x,Boolean fix_y,Boolean fix_z) {
		super(species);
		xcoor=new Coordinate(x,fix_x);
		ycoor=new Coordinate(y,fix_y);
		zcoor=new Coordinate(z,fix_z);
	}
	public Atom(String species, Double x, Double y, Double z, Boolean fix_x,Boolean fix_y,Boolean fix_z) {
		//super();
		try {
			atomSpecies = ChemicalElements.valueOf(species);
		}catch(IllegalArgumentException e) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Invalid atom found in Atom class!"+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
		}
		xcoor=new Coordinate(x,fix_x);
		ycoor=new Coordinate(y,fix_y);
		zcoor=new Coordinate(z,fix_z);
	}
	public void mulX(Double mul) {
		if (mul!=null) {
			double tmp=xcoor.getX();
			xcoor.setX(tmp*mul);}
	}
	public void mulY(Double mul) {
		if (mul!=null) {
			double tmp=ycoor.getX();
			ycoor.setX(tmp*mul);}
	}
	public void mulZ(Double mul) {
		if (mul!=null) {
			double tmp=zcoor.getX();
			zcoor.setX(tmp*mul);}
	}
	
	public Coordinate getXcoor() {
		return xcoor;
	}
	public void setXcoor(Coordinate xcoor) {
		this.xcoor = xcoor;
	}
	public Coordinate getYcoor() {
		return ycoor;
	}
	public void setYcoor(Coordinate ycoor) {
		this.ycoor = ycoor;
	}
	public Coordinate getZcoor() {
		return zcoor;
	}
	public void setZcoor(Coordinate zcoor) {
		this.zcoor = zcoor;
	}
}
