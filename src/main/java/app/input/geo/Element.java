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

public class Element extends Chemical{
	/**
	 * 
	 */
	private static final long serialVersionUID = 1452087912861807366L;
	
	
	private String pseudoPotFile;
	private boolean pseudoValid;
	private Double hubbardU;
	
	
	public Element(ChemicalElements species) {
		super(species);
		pseudoPotFile = null;pseudoValid=false;
		hubbardU = 0.0;
//		try {
//			ChemicalElements enumElem = ChemicalElements.valueOf(species);
//			atomMass=enumElem.getAtomicMass();
//		}catch(IllegalArgumentException e) {
//			Alert alert1 = new Alert(AlertType.INFORMATION);
//	    	alert1.setTitle("Error");
//	    	alert1.setContentText("Exception in Element class!"+e.getMessage());
//	    	alert1.showAndWait();
//			e.printStackTrace();
//		}
	}
	public Element(ChemicalElements species, Double hubb) {
		super(species);
		pseudoPotFile = null;pseudoValid=false;
		hubbardU = hubb;
//		try {
//			ChemicalElements enumElem = ChemicalElements.valueOf(species);
//			atomMass=enumElem.getAtomicMass();
//		}catch(IllegalArgumentException e) {
//			Alert alert1 = new Alert(AlertType.INFORMATION);
//	    	alert1.setTitle("Error");
//	    	alert1.setContentText("Exception in Element class!"+e.getMessage());
//	    	alert1.showAndWait();
//			e.printStackTrace();
//		}
	}
	public Element(String species, Double hubb) {
		//super();
		pseudoPotFile = null;pseudoValid=false;
		hubbardU = hubb;
		try {
			atomSpecies = ChemicalElements.valueOf(species);
			atomMass=atomSpecies.getAtomicMass();
		}catch(IllegalArgumentException e) {
			Alert alert1 = new Alert(AlertType.INFORMATION);
	    	alert1.setTitle("Error");
	    	alert1.setContentText("Exception in Element class!"+e.getMessage());
	    	alert1.showAndWait();
			e.printStackTrace();
		}
	}
	
	public Double getAtomMass() {
		return atomMass;
	}
	public void setAtomMass(Double atomMass) {
		this.atomMass = atomMass;
	}
	public String getPseudoPotFile() {
		return pseudoPotFile;
	}
	public void setPseudoPotFile(String pseudoPotFile) {
		this.pseudoPotFile = pseudoPotFile;
	}
	public Double getHubbardU() {
		return hubbardU;
	}
	public void setHubbardU(Double hubbardU) {
		if (hubbardU!=null) this.hubbardU = hubbardU;
	}
	public boolean isPseudoValid() {
		return pseudoValid;
	}
	public void setPseudoValid(boolean pseudoValid) {
		this.pseudoValid = pseudoValid;
	}
}
