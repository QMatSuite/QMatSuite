package app.centerwindow;

import java.util.ArrayList;

import com.consts.ChemicalElements;
import com.consts.Constants.EnumFileCategory;
import com.error.ShowAlert;

import app.input.Cell;
import app.input.geo.Atom;
import javafx.scene.control.Alert.AlertType;

public class FileDataClass {
	private ArrayList<ArrayList<Double>> energyArray;//Ry
	private ArrayList<Double> fermiLevel;//eV
	private ArrayList<Double> homoLevel;//eV
	private ArrayList<ArrayList<Double>> totalMag;//Bohr mag/cell
	private ArrayList<ArrayList<Double>> absoluteMag;//Bohr mag/cell
	private ArrayList<ArrayList<Double>> dosArray;
	private ArrayList<String> dosHeader;
	public Double fermiDos=null;
	public EnumFileCategory fileCategory=null;
	
	private ArrayList<ArrayList<Atom>> atomicPositions;
	private Double alat = null;
	private ArrayList<Cell> cellParameter;
	
	public int nstep=1;
	public boolean isJobDone=false;
	public boolean hasScf=false;//true when there exist scf steps inside the output file. Not necessary means that it is a scf calculation
	public boolean hasScfFinished=false;
	public boolean isMD=false;
	public boolean isMDFinished=false;
	public boolean isOpt=false;
	public boolean isOptFinished=false;
	public boolean isNscf=false;
	public boolean isNscfFinished=false;
	public boolean isDos=false;
	public boolean isDosFinished=false;
	
	//will be true when one scf just finished. Will be set back to false when one new mag is read
	private boolean flagScfFinishedForTotalMag=false;
	private boolean flagScfFinishedForAbsMag=false;
	
	public FileDataClass() {
		energyArray = new ArrayList<ArrayList<Double>>();
		fermiLevel = new ArrayList<Double>();
		homoLevel = new ArrayList<Double>();
		totalMag = new ArrayList<ArrayList<Double>>();
		absoluteMag = new ArrayList<ArrayList<Double>>();
		dosArray = new ArrayList<ArrayList<Double>>();
		dosHeader = new ArrayList<String>();
		atomicPositions = new ArrayList<ArrayList<Atom>>();
		cellParameter = new ArrayList<Cell>();
	}
	public void clearAll() {
		clearEnergyArray();
	}
	public void parseAlat(String strLine) {
		if(strLine==null || !strLine.contains("=")) return;
		String[] splitted = strLine.trim().split("=");
		//remove everything except numbers (0-9) or dot (.) or minus sign (-)
		try {
			double alatTmp = Double.valueOf(splitted[1].replaceAll("[^\\d.-]", ""));
			if(this.alat!=null && this.alat!=alatTmp) {
				ShowAlert.showAlert(AlertType.INFORMATION, "Warning", "alat not consistent at different steps!");
			}
			this.alat = alatTmp;
		}
		catch(Exception e) {
			e.printStackTrace();
		}
	}
	public void addNewAtomPosition() {
		atomicPositions.add(new ArrayList<Atom>());
	}
	public void addNewCell() {
		cellParameter.add(new Cell());
	}
	public boolean addCellParameter(String strLine) {
		
		String[] splitted = strLine.trim().split("\\s+");//split the string by whitespaces
		if(splitted.length<3) {return false;}//end of one cell_para
		
		Double x=null,
		y=null,
		z=null;
		try {
			x = Double.valueOf(splitted[0]);
			y = Double.valueOf(splitted[1]);
			z = Double.valueOf(splitted[2]);
		}catch(Exception e) {
			return false;
		}
		if(x==null || y==null || z==null) {return false;}
		
		cellParameter.get(cellParameter.size()-1).addCoor(x, y, z);
		
		return true;
	}
	public boolean addAtomicPosition(String strLine) {
		//return false if no atom position is added
		if(strLine==null || strLine.isEmpty() || strLine.trim().length()==0) {return false;}
		String[] splitted = strLine.trim().split("\\s+");//split the string by whitespaces
		if(splitted.length<4) {return false;}
		ChemicalElements atomSpecies=null;
		Double x=null,
		y=null,
		z=null;
		try {
			atomSpecies = ChemicalElements.valueOf(splitted[0]);
			x = Double.valueOf(splitted[1]);
			y = Double.valueOf(splitted[2]);
			z = Double.valueOf(splitted[3]);
		}catch(Exception e) {
			return false;
		}
		if(atomSpecies==null || x==null || y==null || z==null) {return false;}
		atomicPositions.get(atomicPositions.size()-1).add(new Atom(atomSpecies,x,y,z));
		return true;
	}
	public ArrayList<ArrayList<Double>> getDosArray() {
		return dosArray;
	}
	public ArrayList<String> getDosHeader() {
		return dosHeader;
	}
	public void clearEnergyArray() {
		for(ArrayList<Double> ard:energyArray) {
			if(ard!=null) {ard.clear();}
		}
		for(ArrayList<Double> ard:totalMag) {
			if(ard!=null) {ard.clear();}
		}
		for(ArrayList<Double> ard:absoluteMag) {
			if(ard!=null) {ard.clear();}
		}
		for(ArrayList<Double> ard:dosArray) {
			if(ard!=null) {ard.clear();}
		}
		for(ArrayList<Atom> ard:atomicPositions) {
			if(ard!=null) {ard.clear();}
		}
		energyArray.clear();
		fermiLevel.clear();
		homoLevel.clear();
		totalMag.clear();
		absoluteMag.clear();
		dosArray.clear();
		dosHeader.clear();
		
		atomicPositions.clear();
		alat = null;
		cellParameter.clear();
		
		
		nstep=1;fermiDos=null;
		isJobDone=false;
		hasScf=false;hasScfFinished=false;isMD=false;isMDFinished=false;isOpt=false;isOptFinished=false;
		isNscf=false;isNscfFinished=false;isDos=false;isDosFinished=false;
		
		flagScfFinishedForTotalMag=false;
		flagScfFinishedForAbsMag=false;
	}
	public void addTotalEnergy(double ene, boolean isFinal) {
		//here, ene and isFinal are primitive types that CANNOT be null
		//energyArray==null shouldn't happen
		if(energyArray.isEmpty()) {energyArray.add(new ArrayList<Double>());}
		energyArray.get(energyArray.size()-1).add(ene);
		if(isFinal) {energyArray.add(new ArrayList<Double>());
		flagScfFinishedForTotalMag=true;
		flagScfFinishedForAbsMag=true;}
	}
	public void addMag(double mag, boolean isTotal) {
		ArrayList<ArrayList<Double>> tmpMag = isTotal?totalMag:absoluteMag;
		//tmpMag==null shouldn't happen
		if(tmpMag.isEmpty()) {tmpMag.add(new ArrayList<Double>());}
		tmpMag.get(tmpMag.size()-1).add(mag);
		if(flagScfFinishedForTotalMag&&isTotal) {flagScfFinishedForTotalMag=false;tmpMag.add(new ArrayList<Double>());}
		if(flagScfFinishedForAbsMag&&!isTotal) {flagScfFinishedForAbsMag=false;tmpMag.add(new ArrayList<Double>());}
	}
	public ArrayList<ArrayList<Double>> getEnergyArray(){
		return this.energyArray;
	}
	public void setFermi(double fl) {
		fermiLevel.add(fl);
	}
	public void setHomo(double hm) {
		homoLevel.add(hm);
	}
	public void addDosRow(String line) {
		ArrayList<Double> al = new ArrayList<Double>();
		String[] splitted = line.trim().split("\\s+");//split the string by whitespaces
		try {
			for(int i=0;i<splitted.length;i++) {
				al.add(Double.valueOf(splitted[i]));
			}	
			dosArray.add(al);
		}
		catch(Exception e) {
			e.printStackTrace();
		}
	}
	public void addDosHeader(String line) {
		line = line.replace("#", "");
		try {
			String[] parts1 = line.split("[\\)]");
			String[] parts2 = line.split("=");
			String[] parts3 = parts2[1].split("e");
			fermiDos=Double.valueOf(parts3[0]);
			dosHeader.clear();
			for(int i=0;i<parts1.length-1;i++) {
				dosHeader.add(parts1[i]+")");
			}
		}
		catch(Exception e) {
			e.printStackTrace();
		}
	}
	public String toString() {
		String strTmp = "";
		
		if(EnumFileCategory.dos.equals(fileCategory)) {
			//DOS data file
			strTmp+="DOS data file.\n";

			if(dosHeader.size()>0) {
				strTmp+=("Fermi level DOS: "+(fermiDos==null?"null":Double.toString(fermiDos))+"\n");
				strTmp+=dosHeader.get(0);
			}
			if(dosArray.size()>0 && dosArray.get(0).size()>0 && dosArray.get(dosArray.size()-1).size()>0) {
				strTmp+=("(E DOS) from "+Double.toString(dosArray.get(0).get(0))+" to "+
						Double.toString(dosArray.get(dosArray.size()-1).get(0))+"\n");
			}
			
		}
		else if(EnumFileCategory.stdout.equals(fileCategory)) {
			//stdout file
			strTmp+="Standard output file.\n";
			//calculation type
			strTmp+="Detected calculation type:";
			if(nstep==1 && hasScf) {strTmp+="SCF,";}
			if(isMD) {strTmp+="MD,";}
			if(isOpt) {strTmp+="Optimization,";}
			if(isNscf) {strTmp+="NSCF,";}
			if(isDos) {strTmp+="DOS,";}
			
			//finished or not
			if(nstep==1 && hasScf) {strTmp+=(hasScfFinished?"SCF finished.":"SCF not finished.")+"\n";}
			if(isMD) {strTmp+=(isMDFinished?"MD finished.":"MD not finished.")+"\n";}
			if(isOpt) {strTmp+=(isOptFinished?"Optimization finished.":"Optimization not finished.")+"\n";}
			if(isNscf) {strTmp+=(isNscfFinished?"NSCF finished.":"NSCF not finished.")+"\n";}
			if(isDos) {strTmp+=(isDosFinished?"DOS finished.":"DOS not finished.")+"\n";}
			
			//the whole job finished or not (last line of the output file)
			strTmp+=(isJobDone?"Job done.\n":"Job not done yet.\n");
			
			//total energy
			int cnt = 0;
			strTmp+="Total energy (Ry):";
			for(ArrayList<Double> ard:energyArray) {
				if(ard!=null) {
					cnt++;
					if(ard.isEmpty()) {continue;}
					strTmp+=("Step "+Integer.toString(cnt)+": ");
					for(Double val:ard) {
						if(val!=null) {strTmp+=(val.toString()+",");}
					}
					strTmp+="\n";
				}
			}
			
			//magnetization
			int cnt_mag = 0;
			if(!totalMag.isEmpty() || !absoluteMag.isEmpty()) {
				strTmp+="Total magnetization (Bohr mag/cell):";
				for(ArrayList<Double> ard:totalMag) {
					if(ard!=null) {
						cnt_mag++;
						if(ard.isEmpty()) {continue;}
						strTmp+=("Step "+Integer.toString(cnt_mag)+": ");
						for(Double val:ard) {
							if(val!=null) {strTmp+=(val.toString()+",");}
						}
						strTmp+="\n";
					}
				}
				cnt_mag = 0;
				strTmp+="Absolute magnetization (Bohr mag/cell):";
				for(ArrayList<Double> ard:absoluteMag) {
					if(ard!=null) {
						cnt_mag++;
						if(ard.isEmpty()) {continue;}
						strTmp+=("Step "+Integer.toString(cnt_mag)+": ");
						for(Double val:ard) {
							if(val!=null) {strTmp+=(val.toString()+",");}
						}
						strTmp+="\n";
					}
				}
			}
			
			//Fermi
			strTmp+="Fermi energy: ";
			if(fermiLevel.isEmpty()) {strTmp+="Unknown\n";}
			else {
				for(Double val:fermiLevel) {
					if(val!=null) {strTmp+=(val.toString()+",");}
				}
				strTmp+=" eV\n";
			}
			//HOMO
			strTmp+="Highest occupied level: ";
			if(homoLevel.isEmpty()) {strTmp+="Unknown\n";}
			else {
				for(Double val:homoLevel) {
					if(val!=null) {strTmp+=(val.toString()+",");}
				}
				strTmp+=" eV\n";
			}
			
			//
			if(atomicPositions.size()>0) {
				strTmp+="ATOMIC_POSITIONS: "+Integer.toString(atomicPositions.size())+"\n";
				strTmp+="Last position:\n";
				for(Atom atomTmp : atomicPositions.get(atomicPositions.size()-1)) {
					strTmp+=(atomTmp.printPositions()+"\n");
				}
			}
			if(cellParameter.size()>0) {
				strTmp+="CELL_PARAMETERS: "+Integer.toString(cellParameter.size())+"\n";
				strTmp+=("Last cell:\n"+cellParameter.get(cellParameter.size()-1).toString()+"\n");
			}
			if(alat!=null) {
				strTmp+="alat: "+Double.toString(alat)+"\n";
			}
		
		}
		strTmp+="\n";
		return strTmp;
	}
}
