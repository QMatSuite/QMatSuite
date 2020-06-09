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

import java.io.Serializable;

import com.consts.ChemicalElements;

import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;

public class Atom implements Serializable{
	/**
	 * 
	 */
	private static final long serialVersionUID = 2080346685186523233L;
	
	private ChemicalElements atomSpecies;
	//coordinates "as is"
	private Coordinate xcoor;
	private Coordinate ycoor;
	private Coordinate zcoor;
	//for magnet
	private Double mag;private Double angle1;private Double angle2;

	
	public Atom(ChemicalElements species, Double x, Double y, Double z, Boolean fix_x,Boolean fix_y,Boolean fix_z) {
		atomSpecies = species;
		xcoor=new Coordinate(x,fix_x);
		ycoor=new Coordinate(y,fix_y);
		zcoor=new Coordinate(z,fix_z);
		mag=0.0;angle1=0.0;angle2=0.0;
	}
	public Atom(String species, Double x, Double y, Double z, Boolean fix_x,Boolean fix_y,Boolean fix_z) {
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
		mag=0.0;angle1=0.0;angle2=0.0;
	}
	
	public ChemicalElements getAtomSpecies() {
		return atomSpecies;
	}
	public void setAtomSpecies(ChemicalElements atomSpecies) {
		this.atomSpecies = atomSpecies;
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
	public Double getMag() {
		return mag;
	}
	public void setMag(Double mag) {
		if (mag!=null) this.mag = mag;
	}
	public Double getAngle1() {
		return angle1;
	}
	public void setAngle1(Double angle1) {
		if (angle1!=null) this.angle1 = angle1;
	}
	public Double getAngle2() {
		return angle2;
	}
	public void setAngle2(Double angle2) {
		if (angle2!=null) this.angle2 = angle2;
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
